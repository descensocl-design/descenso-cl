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
        # Markdown editorial: los subtítulos '##' deben ser encabezados, no párrafos.
        body_parts = []
        for x in paragraphs:
            value = x.strip()
            if value.startswith('## '):
                body_parts.append(f'<h2>{esc(value[3:])}</h2>')
            elif value.startswith('### '):
                body_parts.append(f'<h3>{esc(value[4:])}</h3>')
            else:
                body_parts.append(f'<p>{esc(value)}</p>')
        body = '\n'.join(body_parts)
        extra_images = post.get('images') if isinstance(post.get('images'), list) else []
        extra_images = list(dict.fromkeys(
            safe_https(x) for x in extra_images
            if safe_https(x) and safe_https(x) != image
        ))[:60]
        gallery_html = ''
        if extra_images:
            # Repartir las fotos dentro del relato, manteniendo el orden de la fuente.
            # En fotoreportajes extensos usar grupos en dos columnas para evitar
            # 10-15 imágenes verticales consecutivas por párrafo.
            paragraph_positions = [i for i, part in enumerate(body_parts) if part.startswith('<p>')]
            slots = max(1, len(paragraph_positions))
            groups = [[] for _ in range(slots)]
            for j, url in enumerate(extra_images):
                slot = min(slots - 1, j * slots // len(extra_images))
                groups[slot].append(url)
            for slot, urls in enumerate(groups):
                if not urls:
                    continue
                figures = []
                for url in urls:
                    figures.append(
                        f'<figure class="article-inline-photo"><a href="{esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Ver fotografía original en tamaño completo">'
                        f'<img src="{esc(url)}" alt="Fotografía oficial de la noticia: {esc(title)}" loading="lazy" decoding="async"></a></figure>'
                    )
                gallery_class = ' article-photo-run-grid' if len(urls) >= 4 else ''
                group_html = f'<div class="article-photo-run{gallery_class}">' + ''.join(figures) + '</div>'
                if paragraph_positions:
                    body_parts[paragraph_positions[slot]] += group_html
                else:
                    body_parts.append(group_html)
            body = '\n'.join(body_parts)
        # Insertar reproductores únicamente cuando existe una URL de video válida.
        video_url = safe_https(post.get('video_embed') or post.get('youtube') or post.get('video_url') or post.get('video'))
        video_html = ''
        if video_url:
            parsed = urlparse(video_url)
            host = parsed.hostname or ''
            identifier = ''
            if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'):
                from urllib.parse import parse_qs
                identifier = parse_qs(parsed.query).get('v', [''])[0]
                if not identifier:
                    match = re.match(r'^/(?:embed|shorts|live)/([A-Za-z0-9_-]{11})', parsed.path)
                    identifier = match.group(1) if match else ''
            elif host == 'youtu.be':
                identifier = parsed.path.strip('/')
            if re.fullmatch(r'[A-Za-z0-9_-]{11}', identifier):
                url = f'https://www.youtube-nocookie.com/embed/{identifier}'
                video_html = f'<figure class="article-video"><iframe src="{esc(url)}" title="Video de la noticia" loading="lazy" allowfullscreen allow="accelerometer; autoplay; encrypted-media; picture-in-picture"></iframe></figure>'
            elif host in ('vimeo.com', 'www.vimeo.com', 'player.vimeo.com'):
                match = re.search(r'/(?:video/)?(\d+)', parsed.path)
                if match:
                    video_html = f'<figure class="article-video"><iframe src="https://player.vimeo.com/video/{match.group(1)}" title="Video de la noticia" loading="lazy" allowfullscreen></iframe></figure>'
            elif host in ('www.pinkbike.com', 'pinkbike.com') and re.match(r'^/(?:video|embed)/', parsed.path):
                video_html = f'<figure class="article-video"><iframe src="{esc(video_url)}" title="Video original de Pinkbike" loading="lazy" allowfullscreen></iframe></figure>'
        if video_html:
            body_parts.insert(min(2, len(body_parts)), video_html)
            body = '\n'.join(body_parts)
        elif ('video' in title.lower() or 'fails' in title.lower()) and safe_https(post.get('link')):
            source_video = safe_https(post.get('link'))
            body = (f'<aside class="article-video-source"><strong>VIDEO ORIGINAL</strong><p>Esta noticia contiene material audiovisual en la fuente. No hay un enlace de inserción verificado.</p>'
                    f'<a href="{esc(source_video)}" target="_blank" rel="noopener noreferrer">VER VIDEO EN LA FUENTE ORIGINAL ↗</a></aside>') + body
        video_collection = post.get('official_video_collection')
        if isinstance(video_collection,dict) and video_collection.get('entries'):
            collection_source = safe_https(video_collection.get('source'))
            if collection_source:
                entries = video_collection.get('entries',[])[:30]
                collection_html = '<section class="article-video-collection"><h2>' + esc(video_collection.get('heading','VIDEOS EN LA FUENTE ORIGINAL')) + '</h2>'
                collection_html += '<p>' + esc(video_collection.get('note','')) + '</p>'
                count_embeds = 0
                for entry in entries:
                    title_video = str(entry.get('title','')) if isinstance(entry,dict) else str(entry)
                    description = str(entry.get('description','')) if isinstance(entry,dict) else ''
                    embed = safe_https(entry.get('embed')) if isinstance(entry,dict) else ''
                    collection_html += '<div class="article-video-entry"><h3>' + esc(title_video) + '</h3>'
                    if description:
                        collection_html += '<p>' + esc(description) + '</p>'
                    if embed and embed.startswith('https://www.youtube-nocookie.com/embed/'):
                        collection_html += '<div class="article-video-player"><iframe src="' + esc(embed) + '" title="' + esc(title_video) + '" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div>'
                        count_embeds += 1
                    collection_html += '</div>'
                if not count_embeds:
                    collection_html += '<a href="' + esc(collection_source) + '" target="_blank" rel="noopener noreferrer">VER REPRODUCTORES EN PINKBIKE ↗</a>'
                collection_html += '</section>'
                marker = str(video_collection.get('marker') or '')
                if video_collection.get('placement') == 'inline_at_marker' and marker.startswith('## '):
                    marker_html = '<h2>' + esc(marker[3:]) + '</h2>'
                    if marker_html in body:
                        body = body.replace(marker_html, collection_html, 1)
                    else:
                        body += collection_html
                else:
                    body += collection_html
        # Nota editorial fechada para corregir hechos que cambiaron tras publicar.
        correction = post.get('editorial_update')
        if isinstance(correction,dict) and correction.get('paragraphs'):
            items = correction.get('paragraphs',[])
            if isinstance(items,list):
                note = '<aside class="article-editorial-update"><strong>' + esc(correction.get('heading','ACTUALIZACIÓN EDITORIAL')) + '</strong>'
                for para in items:
                    note += '<p>' + esc(para) + '</p>'
                correction_source = safe_https(correction.get('source'))
                if correction_source:
                    note += '<p><a href="' + esc(correction_source) + '" target="_blank" rel="noopener noreferrer">VER FUENTE DE LA ACTUALIZACIÓN ↗</a></p>'
                note += '</aside>'
                body = note + body
        source = safe_https(post.get('link'))
        source_name = str(post.get('source_name') or (urlparse(source).hostname or '').removeprefix('www.') or 'Fuente no especificada')
        photo_credit = str(post.get('image_credit') or ('Descenso.cl (gráfica de categoría)' if '/assets/portadas/' in image else 'Crédito no especificado'))
        source_detail = (f'<a href="{esc(source)}" target="_blank" rel="noopener noreferrer">{esc(source_name)}</a>' if source else esc(source_name))
        credits_html = (
            '<div class="article-credits" aria-label="Fuentes y créditos">'
            f'<p>Información: {source_detail}</p>'
            f'<p>Fotografía: {esc(photo_credit)}</p>'
            '</div>'
        )
        article_slug = path.strip('/').split('/')[-1]
        comments_html = (
            f'<section id="comments" class="comments-section" data-article="{esc(article_slug)}">'
            '<h2>COMENTARIOS <span class="comment-count" data-comment-count>0</span></h2>'
            '<p class="comments-status" data-comments-status>Cargando comentarios…</p>'
            '<div class="comments-list" data-comments-list></div>'
            '<form class="comment-form" hidden>'
            '<div class="comment-controls"><label>Nombre <input name="name" maxlength="40" minlength="2" required placeholder="Tu nombre"></label>'
            '<label class="comment-anon"><input type="checkbox" name="anonymous"> Comentar anónimo</label></div>'
            '<label>Comentario <textarea name="message" minlength="12" maxlength="1500" rows="5" required placeholder="¿Qué opinas de esta noticia?"></textarea></label>'
            '<div class="comment-honeypot" aria-hidden="true"><label>Sitio web <input name="website" tabindex="-1" autocomplete="off"></label></div>'
            '<button type="submit">ENVIAR COMENTARIO</button></form></section>'
        )
        # Navegación interna y lecturas relacionadas por disciplina.
        related_candidates = []
        for other in posts:
            if not isinstance(other,dict) or other is post or not other.get('title'):
                continue
            other_path = route(other)
            if other_path == path:
                continue
            relevance = (3 if str(other.get('category','')).casefold() == category.casefold() else 0)
            relevance += (1 if str(other.get('date','')) >= date else 0)
            related_candidates.append((relevance, str(other.get('date','')),other,other_path))
        related_candidates.sort(key=lambda item:(item[0],item[1]),reverse=True)
        related_html = '<section class="article-related" aria-label="Noticias relacionadas"><h2>SEGUIR LEYENDO</h2><div class="article-related-grid">'
        for _,_,other,other_path in related_candidates[:3]:
            other_image = image_for(other)
            related_html += ('<a class="article-related-card" href="' + esc(other_path) + '">'
                             + '<img src="' + esc(other_image) + '" alt="" loading="lazy" decoding="async">'
                             + '<span>' + esc(str(other.get('category') or 'Mountain Bike').upper()) + '</span>'
                             + '<strong>' + esc(other['title']) + '</strong></a>')
        related_html += '</div></section>'
        # Compartir con título real; WhatsApp utiliza texto y enlace del artículo.
        from urllib.parse import quote
        share_text = title + ' — ' + DOMAIN + path
        share_html = ('<nav class="article-share" aria-label="Compartir noticia">'
                      '<span>COMPARTIR NOTICIA</span>'
                      '<a href="https://api.whatsapp.com/send?text=' + esc(quote(share_text)) + '" target="_blank" rel="noopener noreferrer" aria-label="Compartir por WhatsApp">WHATSAPP ↗</a>'
                      '<a href="https://www.facebook.com/sharer/sharer.php?u=' + esc(quote(DOMAIN + path)) + '" target="_blank" rel="noopener noreferrer" aria-label="Compartir en Facebook">FACEBOOK ↗</a>'
                      '<button type="button" class="article-copy-link" data-copy-article-url="' + esc(DOMAIN + path) + '">COPIAR ENLACE</button>'
                      '<span class="article-share-feedback" aria-live="polite"></span></nav>')
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
<figure class="article-figure"><img class="article-cover" src="{esc(image)}" alt="Imagen de la noticia: {esc(title)}" loading="eager" decoding="async"><figcaption>{'DESCENSO.CL' if '/assets/portadas/' in image else esc(str(post.get('image_credit') or ''))}</figcaption></figure>
{share_html}<div class="article-copy">{body}</div>{gallery_html}{credits_html}{related_html}{share_html}{comments_html}
<footer><strong>DESCENSO<span>.CL</span></strong><p>DOWNHILL · ENDURO · XC · FREERIDE</p><a href="/">VOLVER A LA PORTADA ↗</a></footer></main><script src="/comments.js" defer></script><script src="/article-extras.js" defer></script><script src="/analytics.js" defer></script></body></html>"""
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
