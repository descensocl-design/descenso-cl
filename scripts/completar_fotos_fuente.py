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

def imagen_del_rss(item, url):
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
    for candidata in candidatas:
        imagen = urljoin(url, candidata)
        u = urlsplit(imagen)
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            continue
        if any(v in u.path.lower() for v in ("avatar", "logo", "pixel", "tracking", "sprite")):
            continue
        return imagen
    return ""

def main():
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if not isinstance(posts, list):
        raise SystemExit("Formato posts.json inválido")
    pendientes = {}
    for post in posts:
        if not isinstance(post, dict) or not post.get("auto_published") or post.get("image"):
            continue
        url = normalizar(post.get("link", ""))
        if url:
            pendientes[url] = post
    if not pendientes:
        print("Sin publicaciones automáticas pendientes de imagen")
        return
    agregadas = 0
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
            imagen = imagen_del_rss(item, url)
            if not imagen:
                continue
            post = pendientes.pop(url)
            post["image"] = imagen
            post["image_credit"] = f"{fuente} / imagen de la noticia original (fotógrafo por confirmar)"
            post["image_source_url"] = url
            agregadas += 1
            print(f"FOTO: {post.get('title')}: {imagen}")
    if agregadas:
        POSTS.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Fotos incorporadas: {agregadas}. Pendientes: {len(pendientes)}.")

if __name__ == "__main__":
    main()
