#!/usr/bin/env python3
"""Genera páginas estáticas, sitemap y robots para Cloudflare Pages."""
import json, html, re, unicodedata
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = 'https://descenso.cl'

def slugify(value):
    value = unicodedata.normalize('NFD', str(value))
    value = ''.join(c for c in value if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')[:85] or 'noticia'

def route(post):
    permalink = str(post.get('permalink') or '')
    if re.fullmatch(r'/noticias/[a-z0-9-]+/', permalink):
        return permalink
    date = str(post.get('date') or '')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        date = 'sin-fecha'
    return f'/noticias/{date}-{slugify(post.get("title", "noticia"))}/'

def esc(value):
    return html.escape(str(value or ''), quote=True)

def safe_https(value):
    try:
        u = urlparse(str(value or ''))
        return str(value) if u.scheme == 'https' and u.netloc else ''
    except ValueError:
        return ''

def image_for(post):
    image = safe_https(post.get('image'))
    if image:
        return image
    category = str(post.get('category', '')).lower()
    filename = category if category in ('downhill', 'enduro', 'freeride', 'xc') else 'mundo'
    return f'{DOMAIN}/assets/portadas/{filename}.svg'

def build():
    posts = json.loads((ROOT/'data/posts.json').read_text(encoding='utf-8'))
    if not isinstance(posts, list):
        raise ValueError('posts.json debe contener una lista')
    base = ROOT/'noticias'
    base.mkdir(exist_ok=True)
    # Eliminar solo las páginas previamente generadas; no tocar archivos manuales.
    for marker in base.glob('*/.generada-descenso'):
        folder = marker.parent
        (folder/'index.html').unlink(missing_ok=True)
        marker.unlink()
        try: folder.rmdir()
        except OSError: pass
    seen = set()
    urls = [('/', '')]
    for post in posts:
        if not isinstance(post, dict) or not post.get('title'):
            continue
        path = route(post)
        if path in seen:
            raise ValueError(f'URL duplicada: {path}')
        seen.add(path)
        title = str(post['title'])
        excerpt = str(post.get('excerpt') or '')[:280]
        date = str(post.get('date') or '')
        category = str(post.get('category') or 'Mountain Bike')
        image = image_for(post)
        paragraphs = post.get('body') or []
        if isinstance(paragraphs, str): paragraphs = [paragraphs]
        paragraphs = [str(x) for x in paragraphs if str(x).strip()]
        # Evitar repetir el resumen como primer párrafo del artículo.
        if paragraphs and re.sub(r'\s+', ' ', paragraphs[0]).strip().casefold() == re.sub(r'\s+', ' ', excerpt).strip().casefold():
            paragraphs = paragraphs[1:]
        body = '\n'.join(f'<p>{esc(x)}</p>' for x in paragraphs)
        source = safe_https(post.get('link'))
        source_html = f'<a class="source-link" href="{esc(source)}" target="_blank" rel="noopener noreferrer">VER FUENTE ORIGINAL ↗</a>' if source else ''
        canonical = DOMAIN + path
        schema = {'@context':'https://schema.org','@type':'NewsArticle','headline':title,'description':excerpt,'datePublished':date,'image':[image],'mainEntityOfPage':canonical,'publisher':{'@type':'Organization','name':'Descenso.cl','url':DOMAIN,'logo':{'@type':'ImageObject','url':DOMAIN+'/logo-descenso.jpg'}}}
        structured = json.dumps(schema,ensure_ascii=False).replace('<','\\u003c')
        page = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090909"><title>{esc(title)} | Descenso.cl</title>
<meta name="description" content="{esc(excerpt)}"><link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article"><meta property="og:site_name" content="Descenso.cl"><meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(excerpt)}"><meta property="og:url" content="{esc(canonical)}"><meta property="og:image" content="{esc(image)}">
<meta name="twitter:card" content="summary_large_image"><link rel="stylesheet" href="/styles.css">
<script type="application/ld+json">{structured}</script></head>
<body><header class="header"><div class="topline"><span>INDEPENDIENTE · DESDE CHILE PARA EL MUNDO</span><a href="https://contacto.descenso.cl/">CONTACTO ↗</a></div>
<div class="brandrow"><a class="brand" href="/" aria-label="Descenso.cl — Inicio"><img class="brand-logo" src="/logo-descenso.jpg" alt="DESCENSO.CL"></a><span class="tagline">DOWNHILL / ENDURO / XC / FREERIDE</span></div>
<nav class="nav" aria-label="Categorías"><a class="navitem" href="/">INICIO</a></nav></header>
<main class="article-page"><a class="back-link" href="/">← VOLVER A NOTICIAS</a><div class="article-tag">{esc(category.upper())}</div>
<h1>{esc(title)}</h1><div class="article-date">{esc(date)}</div><p class="lede">{esc(excerpt)}</p>
<figure class="article-figure"><img class="article-cover" src="{esc(image)}" alt="Imagen de la noticia: {esc(title)}" loading="eager"><figcaption>{'Imagen de referencia de Descenso.cl' if '/assets/portadas/' in image else ('Imagen de archivo autorizada' if post.get('image_approved') else 'Imagen de archivo; revisar derechos de uso')}</figcaption></figure>
<div class="article-copy">{body}</div>{source_html}
<footer><strong>DESCENSO<span>.CL</span></strong><p>DOWNHILL · ENDURO · XC · FREERIDE</p><a href="/">VOLVER A LA PORTADA ↗</a></footer></main></body></html>"""
        folder = ROOT / path.lstrip('/')
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'index.html').write_text(page, encoding='utf-8')
        (folder/'.generada-descenso').write_text('generada\n',encoding='utf-8')
        urls.append((path,date))
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path,date in urls:
        sitemap += f'<url><loc>{DOMAIN}{esc(path)}</loc>' + (f'<lastmod>{esc(date)}</lastmod>' if date else '') + '</url>\n'
    sitemap += '</urlset>\n'
    (ROOT/'sitemap.xml').write_text(sitemap, encoding='utf-8')
    (ROOT/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n',encoding='utf-8')
    print(f'Generadas {len(seen)} páginas de noticias')

if __name__ == '__main__':
    build()
