#!/usr/bin/env python3
"""Publicador conservador de Descenso.cl; simula salvo que se use --publicar.

Lee JSON estructurado desde data/listas-para-publicar/. No interpreta borradores
Markdown ni convierte las declaraciones de Gemini en verificaciones editoriales.
"""
import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

POSTS = Path('data/posts.json')
ENTRADAS = Path('data/listas-para-publicar')
MAX_DIARIO = 3
CATEGORIAS = {'Downhill', 'Enduro', 'Freeride', 'XC', 'Latinoamérica', 'Mundo', 'Chile', 'Araucanía'}
MIN_PALABRAS_NOTA = 50
MIN_PALABRAS_FUENTE = 50


def url_normalizada(value):
    try:
        u = urlsplit(str(value).strip())
        if u.scheme != 'https' or not u.hostname:
            return ''
        return urlunsplit((u.scheme, u.netloc.lower(), u.path.rstrip('/'), '', ''))
    except ValueError:
        return ''


def validar(n):
    if not isinstance(n, dict):
        return 'formato inválido'
    obligatorios = ('title', 'date', 'category', 'excerpt', 'body', 'source_url')
    if any(not n.get(k) for k in obligatorios):
        return 'faltan campos obligatorios'
    if not all(isinstance(n[k], str) for k in ('title', 'date', 'category', 'excerpt', 'source_url')):
        return 'campos de texto inválidos'
    if not isinstance(n['body'], list) or not all(isinstance(p, str) for p in n['body']):
        return 'body debe ser una lista de párrafos'
    if n['category'] not in CATEGORIAS:
        return 'categoría no admitida'
    try:
        if date.fromisoformat(n['date']).isoformat() != n['date']:
            return 'fecha inválida (usar AAAA-MM-DD)'
    except (TypeError, ValueError):
        return 'fecha inválida (usar AAAA-MM-DD)'
    if not url_normalizada(n['source_url']):
        return 'URL de fuente inválida'
    if len(n['title'].strip()) < 15 or len(n['excerpt'].strip()) < 50:
        return 'título o resumen demasiado breve'
    palabras = len(' '.join(n['body']).split())
    if palabras < MIN_PALABRAS_NOTA:
        return 'texto insuficiente (mínimo 50 palabras)'
    if n.get('image'):
        return 'imagen externa requiere revisión de derechos; dejar image vacío'
    if n.get('image_pending_review', False):
        return 'derechos de imagen pendientes'
    if n.get('verified_facts') is not True:
        return 'hechos no verificados'
    if n.get('editorial_approved') is not True:
        return 'sin aprobación editorial'
    palabras_fuente = n.get('source_context_words', 0)
    if isinstance(palabras_fuente, bool) or not isinstance(palabras_fuente, int) or palabras_fuente < MIN_PALABRAS_FUENTE:
        return 'contexto original insuficiente (mínimo 50 palabras)'
    if 'pendiente de verificación' in ' '.join(n['body']).lower():
        return 'el texto contiene advertencia de verificación'
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publicar', action='store_true', help='Actualizar posts.json (por defecto: simulación)')
    args = parser.parse_args()
    if not POSTS.exists():
        raise SystemExit('ERROR: falta data/posts.json; no se crea uno nuevo')
    posts = json.loads(POSTS.read_text(encoding='utf-8'))
    if not isinstance(posts, list):
        raise SystemExit('ERROR: posts.json no contiene una lista')
    existentes = {url_normalizada(p.get('link', '')) for p in posts if isinstance(p, dict)}
    existentes.discard('')
    hoy = date.today().isoformat()
    publicados_hoy = sum(1 for p in posts if isinstance(p, dict) and p.get('date') == hoy and p.get('auto_published'))
    cupos = max(0, MAX_DIARIO - publicados_hoy)
    candidatos = sorted(ENTRADAS.glob('*.json')) if ENTRADAS.exists() else []
    aceptados = []
    for archivo in candidatos:
        try:
            n = json.loads(archivo.read_text(encoding='utf-8'))
            motivo = validar(n)
        except (OSError, ValueError, TypeError) as exc:
            print(f'RECHAZADA {archivo.name}: JSON ilegible ({type(exc).__name__})')
            continue
        enlace = url_normalizada(n.get('source_url', '')) if isinstance(n, dict) else ''
        if not motivo and enlace in existentes:
            motivo = 'URL duplicada'
        if not motivo and len(aceptados) >= cupos:
            motivo = 'límite diario alcanzado'
        if motivo:
            print(f'RECHAZADA {archivo.name}: {motivo}')
            continue
        aceptados.append({
            'title': n['title'].strip(), 'date': n['date'], 'category': n['category'],
            'excerpt': n['excerpt'].strip(), 'image': '', 'youtube': '',
            'body': [p.strip() for p in n['body'] if p.strip()],
            'link': enlace, 'auto_published': True,
        })
        existentes.add(enlace)
        print(f'APTA {archivo.name}: {n["title"]}')
    print(f'Modo: {"PUBLICACIÓN" if args.publicar else "SIMULACIÓN"}')
    print(f'Candidatas: {len(candidatos)} | Aptas: {len(aceptados)} | Cupos: {cupos}')
    if args.publicar and aceptados:
        temporal = POSTS.with_suffix('.json.tmp')
        temporal.write_text(json.dumps(aceptados + posts, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporal.replace(POSTS)
        print(f'Publicadas en posts.json: {len(aceptados)}')
    else:
        print('posts.json NO modificado')


if __name__ == '__main__':
    main()
