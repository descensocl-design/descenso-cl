#!/usr/bin/env python3
"""Descubre fuentes complementarias para Descenso.cl (sin verificar ni publicar).

Entrada: data/noticias_candidatas.json
Salida: data/fuentes_complementarias.json

Consulta Google News RSS como índice de enlaces públicos. Los titulares y
resúmenes encontrados son pistas, NO hechos corroborados. Nunca declara
aprobación editorial ni modifica posts.json.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

ENTRADA = Path('data/noticias_candidatas.json')
SALIDA = Path('data/fuentes_complementarias.json')
MAX_NOTICIAS = 5
MAX_RESULTADOS = 8
TIMEOUT = 15
HEADERS = {'User-Agent': 'DescensoNewsBot/1.0 (+https://descenso.cl)'}


def limpiar(texto):
    return ' '.join(unescape(re.sub(r'<[^>]*>', ' ', texto or '')).split())


def consulta_para(noticia):
    titulo = limpiar(noticia.get('titulo', ''))
    # Acota títulos muy extensos y quita sufijos editoriales que no ayudan.
    titulo = re.split(r'\s*[:|]\s*', titulo, maxsplit=1)[0]
    palabras = re.findall(r"[\w'-]+", titulo, flags=re.UNICODE)
    return ' '.join(palabras[:12])


def descubrir(consulta):
    if not consulta:
        return [], 'Título vacío'
    parametros = urllib.parse.urlencode({
        'q': consulta, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'
    })
    url = 'https://news.google.com/rss/search?' + parametros
    peticion = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            contenido = respuesta.read(750_000)
        raiz = ET.fromstring(contenido)
    except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError, ValueError) as error:
        return [], f'Consulta no disponible: {type(error).__name__}'

    resultados = []
    vistos = set()
    for item in raiz.findall('.//item'):
        enlace = (item.findtext('link') or '').strip()
        titulo = limpiar(item.findtext('title') or '')
        if not enlace.startswith('https://') or not titulo or enlace in vistos:
            continue
        vistos.add(enlace)
        origen = item.find('source')
        resultados.append({
            'titulo': titulo,
            'url_indice': enlace,
            'medio': limpiar(origen.text or '') if origen is not None else '',
            'fecha_publicacion': item.findtext('pubDate') or '',
            'descripcion_indice': limpiar(item.findtext('description') or '')[:350],
            'tipo': 'referencia_por_revisar',
            'contenido_original_leido': False,
            'hechos_corroborrados': False,
        })
        if len(resultados) >= MAX_RESULTADOS:
            break
    return resultados, None


def main():
    if not ENTRADA.exists():
        raise SystemExit(f'ERROR: no existe {ENTRADA}')
    datos = json.loads(ENTRADA.read_text(encoding='utf-8'))
    noticias = datos.get('noticias', [])
    if not isinstance(noticias, list):
        raise SystemExit('ERROR: noticias debe ser una lista')
    salida = []
    for noticia in noticias[:MAX_NOTICIAS]:
        consulta = consulta_para(noticia)
        fuentes, error = descubrir(consulta)
        salida.append({
            'titulo_original': noticia.get('titulo', ''),
            'url_original': noticia.get('url', ''),
            'consulta': consulta,
            'referencias': fuentes,
            'error': error,
            'verificacion_automatica': False,
            'aprobacion_editorial': False,
            'estado': 'fuentes_por_comprobar',
        })
        print(f'{consulta[:65]}: {len(fuentes)} referencias' + (f' | {error}' if error else ''), flush=True)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({
        'actualizado': datetime.now(timezone.utc).isoformat(),
        'advertencia': 'Resultados de índice; no son hechos verificados ni autorizan publicación.',
        'noticias': salida,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Generado: {SALIDA} | Publicación: DESACTIVADA')


if __name__ == '__main__':
    main()
