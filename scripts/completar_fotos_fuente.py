#!/usr/bin/env python3
"""Añade imágenes del RSS de la fuente a noticias ya publicadas sin foto."""
import html
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from io import BytesIO
from PIL import Image

POSTS = Path("data/posts.json")
FEEDS = {
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php",
    "Singletracks": "https://www.singletracks.com/feed/",
    "BikeRumor": "https://bikerumor.com/bike-types/mountain-bike/feed/",
    "E-Mountainbike": "https://ebike-mtb.com/en/feed/",
}
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"

def normalizar(url):
    try:
        u = urlsplit(str(url).strip())
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            return ""
        return urlunsplit(("https", u.netloc.lower(), u.path.rstrip("/"), "", ""))
    except ValueError:
        return ""

def imagenes_del_rss(item, url):
    candidatas = []
    for nodo in item.iter():
        tag = nodo.tag.split("}")[-1].lower()
        ns = nodo.tag.split("}")[0] if "}" in nodo.tag else ""
        tipo = (nodo.attrib.get("type") or "").lower()
        if (tag in ("thumbnail", "content") and "search.yahoo.com/mrss" in ns) or (tag == "enclosure" and tipo.startswith("image/")):
            candidatas.append(nodo.attrib.get("url") or "")
    for texto in (item.findtext(CONTENT), item.findtext("description")):
        for m in re.finditer(r"""<img\b[^>]*\b(?:src|data-src)\s*=\s*["']([^"']+)["']""", texto or "", re.I):
            candidatas.append(html.unescape(m.group(1)))
    resultados = []
    for candidata in candidatas:
        imagen = urljoin(url, candidata)
        u = urlsplit(imagen)
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            continue
        if any(v in u.path.lower() for v in ("avatar", "logo", "pixel", "tracking", "sprite")):
            continue
        key = re.sub(r"/p[0-9]pb([0-9]+)/p[0-9]pb\\1", r"/photo/\\1", imagen)
        if key not in {re.sub(r"/p[0-9]pb([0-9]+)/p[0-9]pb\\1", r"/photo/\\1", x) for x in resultados}:
            resultados.append(imagen)
        if len(resultados) >= 7:
            break
    return resultados

def version_grande(url):
    """Selecciona la versión comprobada de al menos 1000 píxeles de ancho."""
    m = re.search(r"/p[0-9]pb([0-9]+)/p[0-9]pb\1\.(jpe?g|png)(?:[?#].*)?$", url, re.I)
    if not m:
        return url
    ident, ext = m.groups()
    base = urlsplit(url)
    for size in ("p0pb", "p5pb"):
        candidata = urlunsplit((base.scheme, base.netloc, f"/{size}{ident}/{size}{ident}.{ext}", "", ""))
        try:
            req = Request(candidata, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-262143"})
            with urlopen(req, timeout=12) as resp:
                if not resp.headers.get("Content-Type", "").lower().startswith("image/"):
                    continue
                data = resp.read(262144)
            with Image.open(BytesIO(data)) as foto:
                ancho, alto = foto.size
            print(f"Resolución de {size}: {ancho}x{alto} para {ident}", flush=True)
            if ancho >= 1000:
                return candidata
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            print(f"Versión {size} no disponible: {type(exc).__name__}: {exc}", flush=True)
    return url

def main():
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if not isinstance(posts, list):
        raise SystemExit("Formato posts.json inválido")
    actualizadas = 0
    for post in posts:
        if isinstance(post, dict) and post.get("image") and "pinkbike.org/" in post["image"]:
            grande = version_grande(post["image"])
            if grande != post["image"]:
                post["image"] = grande
                actualizadas += 1
    pendientes = {}
    for post in posts:
        if not isinstance(post, dict) or not post.get("auto_published"):
            continue
        url = normalizar(post.get("link", ""))
        if url and (not post.get("image") or len(post.get("images", [])) < 4):
            pendientes[url] = post
    if not pendientes:
        if actualizadas:
            POSTS.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Sin artículos con galerías pendientes; imágenes mejoradas: {actualizadas}")
        return
    agregadas = 0
    galerias = 0
    for fuente, feed in FEEDS.items():
        try:
            req = Request(feed, headers={"User-Agent": "Mozilla/5.0 (compatible; DescensoPhotoBot/1.0)"})
            with urlopen(req, timeout=18) as resp:
                raiz = ET.fromstring(resp.read(2500000))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, ET.ParseError) as exc:
            print(f"{fuente}: RSS no disponible: {type(exc).__name__}: {exc}")
            continue
        for item in raiz.findall(".//item")[:100]:
            url = normalizar(item.findtext("link") or "")
            if url not in pendientes:
                continue
            imagenes = imagenes_del_rss(item, url)
            if not imagenes:
                continue
            post = pendientes.pop(url)
            fotos = [version_grande(imagen) for imagen in imagenes[:6]]
            fotos = list(dict.fromkeys(fotos))
            if not post.get("image"):
                post["image"] = fotos[0]
                agregadas += 1
            # Mantener sólo imágenes originales de esta noticia.
            fotos = [f for f in fotos if f != post["image"]][:5]
            if fotos:
                post["images"] = fotos
                galerias += 1
            post["image_credit"] = post.get("image_credit") or f"{fuente} / fotografías del artículo original (autor por confirmar)"
            post["image_source_url"] = url
            print(f"GALERÍA: {post.get('title')}: {len(fotos)} imágenes adicionales")
    if agregadas or actualizadas or galerias:
        POSTS.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Portadas: {agregadas}. Galerías: {galerias}. Mejoradas: {actualizadas}. Pendientes: {len(pendientes)}.")

if __name__ == "__main__":
    main()
