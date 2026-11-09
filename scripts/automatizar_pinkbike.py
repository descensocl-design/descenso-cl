
#!/usr/bin/env python3
"""Publica hasta cinco noticias diarias desde candidatos RSS de Pinkbike.

No descarga fotografías ajenas. Usa una portada SVG local por categoría.
"""
import argparse
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

CANDIDATAS = Path('data/noticias_ampliadas.json')
CANDIDATAS_RSS = Path('data/noticias_candidatas.json')
POSTS = Path('data/posts.json')
IMAGENES_AUTORIZADAS = Path('data/imagenes_autorizadas.json')
MAX_DIARIO = 5
ZONA = ZoneInfo('America/Santiago')
MODELO = os.getenv('GEMINI_MODEL', 'gemini-flash-lite-latest')


def normalizar_url(url):
    try:
        p = urlsplit(str(url).strip())
        if p.scheme != 'https' or p.hostname not in ('www.pinkbike.com', 'pinkbike.com'):
            return ''
        return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', ''))
    except ValueError:
        return ''


def limpiar(texto):
    texto = re.sub(r'<[^>]+>', ' ', str(texto or ''))
    return re.sub(r'\s+', ' ', html.unescape(texto)).strip()


def contexto_rss(noticia):
    titulo = limpiar(noticia.get('titulo'))
    descripcion = limpiar(noticia.get('descripcion') or noticia.get('contexto_rss'))
    return '\n'.join(p for p in (titulo, descripcion) if p)


def redactar(noticia):
    clave = os.getenv('GEMINI_API_KEY', '').strip()
    if not clave:
        return None, 'falta GEMINI_API_KEY'

    fuente = contexto_rss(noticia)
    contexto = limpiar(noticia.get('contexto_ampliado', ''))
    # Se requiere información sustantiva antes de generar un artículo largo.
    # El extractor es auxiliar; no se publica texto extraído literalmente.
    if len(contexto.split()) >= 100 and noticia.get('origen_contexto_ampliado') == 'pagina_original':
        fuente += '\n\nCONTEXTO DEL ARTÍCULO ORIGINAL:\n' + contexto[:11000]
    if len(fuente.split()) < 95:
        return None, 'información insuficiente para artículo completo'
    instrucciones = (
        'Eres editor de Descenso.cl, medio chileno de mountain bike. '
        'Redacta un artículo original en español usando SOLAMENTE hechos del material suministrado. '
        'Devuelve SOLO JSON válido con claves "title", "excerpt" y "body". '
        'title: titular informativo en español, sin exageraciones. '
        'excerpt: una o dos frases de hasta 220 caracteres. '
        'body: lista de 2 a 6 párrafos, cada uno con hechos diferentes. '
        'Explica cifras, protagonistas, consecuencias y contexto SOLO cuando aparezcan en el material. '
        'No repitas el excerpt en el body ni inventes hechos, resultados, declaraciones o fechas. '
        'No copies frases extensas del original, ni traduzcas párrafos completos literalmente. '
        'No incluyas enlaces ni Markdown. '
        'Si no hay información para al menos 2 párrafos sustanciales, responde SIN_DATOS. '
        'Los hechos proceden de una fuente externa y no están verificados independientemente.\n\n'
        'MATERIAL:\n' + fuente
    )

    endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        + MODELO + ':generateContent'
    )

    payload = {
        'contents': [{'parts': [{'text': instrucciones}]}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 1500
        },
    }

    req = Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': clave
        },
        method='POST',
    )

    try:
        with urlopen(req, timeout=45) as respuesta:
            datos = json.load(respuesta)

        candidatos = datos.get('candidates') or []
        partes = (
            candidatos[0].get('content', {}).get('parts', [])
            if candidatos else []
        )
        texto = '\n'.join(
            p.get('text', '')
            for p in partes
            if isinstance(p, dict)
        ).strip()

    except (
        HTTPError, URLError, TimeoutError,
        ValueError, KeyError, IndexError
    ) as exc:
        return None, f'error de Gemini: {type(exc).__name__}: {exc}'

    if not texto or texto == 'SIN_DATOS':
        return None, 'Gemini no encontró datos suficientes'

    texto = re.sub(
        r'^```(?:json)?\s*|\s*```$',
        '',
        texto,
        flags=re.I
    ).strip()

    try:
        salida = json.loads(texto)
    except json.JSONDecodeError:
        return None, 'Gemini no devolvió JSON válido'

    if not isinstance(salida, dict):
        return None, 'respuesta de Gemini inesperada'

    titulo = salida.get('title')
    resumen = salida.get('excerpt')
    cuerpo = salida.get('body')

    if (
        not isinstance(titulo, str)
        or not isinstance(resumen, str)
        or not isinstance(cuerpo, list)
    ):
        return None, 'faltan campos editoriales'

    titulo = limpiar(titulo)
    resumen = limpiar(resumen)
    cuerpo = [
        limpiar(p)
        for p in cuerpo
        if isinstance(p, str) and limpiar(p)
    ]

    if not (
        10 <= len(titulo) <= 170
        and 15 <= len(resumen) <= 220
        and 2 <= len(cuerpo) <= 6
    ):
        return None, 'longitud editorial inválida'

    if sum(len(p.split()) for p in cuerpo) > 650:
        return None, 'texto demasiado extenso para los datos RSS'

    return {
        'title': titulo,
        'excerpt': resumen,
        'body': cuerpo
    }, None


def categoria(noticia):
    texto = contexto_rss(noticia).lower()

    if re.search(r'\b(downhill|dh|world cup|hardline)\b', texto):
        return 'Downhill'
    if 'enduro' in texto:
        return 'Enduro'
    if 'freeride' in texto:
        return 'Freeride'
    if re.search(r'\b(xc|xco|cross.country)\b', texto):
        return 'XC'

    return 'Mundo'


def imagen_autorizada(url_fuente):
    """Only use images whose permission has been reviewed and entered by the editor."""
    if not IMAGENES_AUTORIZADAS.exists():
        return ''
    try:
        data = json.loads(IMAGENES_AUTORIZADAS.read_text(encoding='utf-8'))
        entry = data.get(url_fuente, {}) if isinstance(data, dict) else {}
        url = entry.get('image', '') if isinstance(entry, dict) else ''
        approved = entry.get('approved') is True if isinstance(entry, dict) else False
        if approved and isinstance(url, str) and url.startswith('https://'):
            return url
    except (OSError, ValueError, TypeError):
        pass
    return ''


def preparar(noticia, hoy):
    if (
        not isinstance(noticia, dict)
        or noticia.get('fuente') != 'Pinkbike'
    ):
        return None, 'fuente no admitida'

    url = normalizar_url(noticia.get('url', ''))
    if not url:
        return None, 'URL de Pinkbike inválida'

    comentarios = noticia.get('comentarios')
    if type(comentarios) is not int or comentarios < 0:
        return None, 'sin número fiable de comentarios'

    if (
        len(limpiar(noticia.get('titulo'))) < 10
        or len(contexto_rss(noticia).split()) < 5
    ):
        return None, 'RSS insuficiente'

    contenido, error = redactar(noticia)
    if error:
        return None, error

    seccion = categoria(noticia)

    return {
        'title': contenido['title'],
        'date': hoy,
        'category': seccion,
        'excerpt': contenido['excerpt'],
        'image': imagen_autorizada(url),
        'youtube': '',
        'body': contenido['body'],
        'link': url,
        'auto_published': True,
        'source_name': 'Pinkbike',
        'editorial_method': 'resumen_original_de_fuente_externa',
        'source_comments_at_selection': comentarios,
    }, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--publicar',
        action='store_true',
        help='Guardar notas; sin esta opción simula'
    )
    args = parser.parse_args()

    origen = CANDIDATAS if CANDIDATAS.exists() else CANDIDATAS_RSS
    if not origen.exists() or not POSTS.exists():
        raise SystemExit(
            'ERROR: faltan noticias_candidatas.json o posts.json'
        )

    datos = json.loads(
        origen.read_text(encoding='utf-8')
    )
    posts = json.loads(
        POSTS.read_text(encoding='utf-8')
    )

    if (
        not isinstance(posts, list)
        or not isinstance(datos, dict)
        or not isinstance(datos.get('noticias'), list)
    ):
        raise SystemExit('ERROR: formato JSON inesperado')

    hoy = datetime.now(ZONA).date().isoformat()

    usados = {
        normalizar_url(p.get('link', ''))
        for p in posts
        if isinstance(p, dict)
    }
    usados.discard('')

    publicados = sum(
        1 for p in posts
        if isinstance(p, dict)
        and p.get('date') == hoy
        and p.get('auto_published') is True
        and p.get('source_name') == 'Pinkbike'
    )

    cupos = max(0, MAX_DIARIO - publicados)

    noticias = sorted(
        (
            n for n in datos['noticias']
            if isinstance(n, dict)
        ),
        key=lambda n: (
            n.get('comentarios')
            if type(n.get('comentarios')) is int
            else -1
        ),
        reverse=True,
    )

    aceptadas = []

    for noticia in noticias:
        if len(aceptadas) >= cupos:
            break

        url = normalizar_url(noticia.get('url', ''))

        if url and url in usados:
            print(
                f'OMITIDA duplicada: {noticia.get("titulo", "")}',
                flush=True
            )
            continue

        nota, motivo = preparar(noticia, hoy)

        if motivo:
            print(
                f'OMITIDA {noticia.get("titulo", "")}: {motivo}',
                flush=True
            )
            continue

        aceptadas.append(nota)
        usados.add(url)

        print(
            f'APTA {nota["title"]} | comentarios: '
            f'{nota["source_comments_at_selection"]}',
            flush=True
        )

    print(
        f'Modo: {"PUBLICAR" if args.publicar else "SIMULAR"}; '
        f'cupos: {cupos}; aptas: {len(aceptadas)}',
        flush=True
    )

    if args.publicar and aceptadas:
        temporal = POSTS.with_suffix('.json.tmp')

        temporal.write_text(
            json.dumps(
                aceptadas + posts,
                ensure_ascii=False,
                indent=2
            ) + '\n',
            encoding='utf-8',
        )

        temporal.replace(POSTS)

        print(
            f'posts.json actualizado: '
            f'{len(aceptadas)} publicaciones',
            flush=True
        )
    else:
        print('posts.json sin modificaciones', flush=True)


if __name__ == '__main__':
    main()
