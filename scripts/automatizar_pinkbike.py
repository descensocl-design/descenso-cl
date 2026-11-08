#!/usr/bin/env python3
"""Prepara o publica hasta cinco notas de Pinkbike al día.

Por defecto simula. --publicar modifica data/posts.json únicamente para notas
con contexto fuente suficiente y redacción válida. No utiliza imágenes externas.
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from crear_borradores import redactar_con_gemini, contexto_de, identificar_categoria

CANDIDATAS = Path('data/noticias_candidatas.json')
POSTS = Path('data/posts.json')
MAX_DIARIO = 5
MIN_FUENTE = 50
MIN_NOTA = 50
ZONA = ZoneInfo('America/Santiago')


def normalizar_url(url):
    try:
        p = urlsplit(str(url).strip())
        if p.scheme != 'https' or p.hostname not in ('www.pinkbike.com', 'pinkbike.com'):
            return ''
        return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', ''))
    except ValueError:
        return ''


def preparar(noticia, hoy):
    if not isinstance(noticia, dict) or noticia.get('fuente') != 'Pinkbike':
        return None, 'fuente no admitida'
    url = normalizar_url(noticia.get('url', ''))
    if not url:
        return None, 'URL de Pinkbike inválida'
    comentarios = noticia.get('comentarios')
    if type(comentarios) is not int or comentarios < 0:
        return None, 'sin número fiable de comentarios'
    titulo = str(noticia.get('titulo') or '').strip()
    contexto = contexto_de(noticia)
    if len(contexto.split()) < MIN_FUENTE:
        return None, f'contexto insuficiente: {len(contexto.split())} palabras'
    if len(titulo) < 15:
        return None, 'título insuficiente'
    texto, error = redactar_con_gemini(noticia)
    if error or not texto:
        return None, error or 'Gemini no devolvió texto'
    if 'pendiente de verificaci' in texto.lower():
        return None, 'Gemini indicó información pendiente'
    parrafos = [p.strip() for p in re.split(r'\n\s*\n', texto) if p.strip()]
    if len(' '.join(parrafos).split()) < MIN_NOTA:
        return None, 'redacción demasiado breve'
    if any(re.search(r'(?i)(^#|^---|^source_url:|^title:)', p) for p in parrafos):
        return None, 'formato inesperado de Gemini'
    resumen = ' '.join(parrafos).strip()[:220]
    if len(resumen) < 50:
        return None, 'resumen insuficiente'
    return {
        'title': titulo,
        'date': hoy,
        'category': identificar_categoria(noticia),
        'excerpt': resumen,
        'image': '',
        'youtube': '',
        'body': parrafos,
        'link': url,
        'auto_published': True,
        'source_name': 'Pinkbike',
        'source_comments_at_selection': comentarios,
    }, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publicar', action='store_true', help='Modificar posts.json; por defecto solo simula')
    args = parser.parse_args()
    if not CANDIDATAS.exists() or not POSTS.exists():
        raise SystemExit('ERROR: faltan data/noticias_candidatas.json o data/posts.json')
    datos = json.loads(CANDIDATAS.read_text(encoding='utf-8'))
    posts = json.loads(POSTS.read_text(encoding='utf-8'))
    if not isinstance(posts, list) or not isinstance(datos.get('noticias'), list):
        raise SystemExit('ERROR: formato JSON inesperado')
    hoy = datetime.now(ZONA).date().isoformat()
    usados = {normalizar_url(p.get('link', '')) for p in posts if isinstance(p, dict)}
    usados.discard('')
    publicados = sum(1 for p in posts if isinstance(p, dict) and p.get('date') == hoy and p.get('auto_published'))
    cupos = max(0, MAX_DIARIO - publicados)
    noticias = sorted(
        (n for n in datos['noticias'] if isinstance(n, dict)),
        key=lambda n: n.get('comentarios') if type(n.get('comentarios')) is int else -1,
        reverse=True,
    )
    aceptadas = []
    for noticia in noticias:
        if len(aceptadas) >= cupos:
            break
        url = normalizar_url(noticia.get('url', ''))
        if url and url in usados:
            print(f'OMITIDA duplicada: {noticia.get("titulo", "")}')
            continue
        # No se llama a Gemini si el texto fuente es insuficiente.
        nota, motivo = preparar(noticia, hoy)
        if motivo:
            print(f'OMITIDA {noticia.get("titulo", "")}: {motivo}')
            continue
        aceptadas.append(nota)
        usados.add(url)
        print(f'APTA {nota["title"]} | comentarios: {nota["source_comments_at_selection"]}')
    print(f'Modo: {"PUBLICAR" if args.publicar else "SIMULAR"}; cupos: {cupos}; aptas: {len(aceptadas)}')
    if args.publicar and aceptadas:
        temporal = POSTS.with_suffix('.json.tmp')
        temporal.write_text(json.dumps(aceptadas + posts, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporal.replace(POSTS)
        print(f'posts.json actualizado: {len(aceptadas)} publicaciones')
    else:
        print('posts.json sin modificaciones')


if __name__ == '__main__':
    main()
