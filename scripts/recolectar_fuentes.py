#!/usr/bin/env python3
"""Reúne material informativo de RSS públicos; no publica ni reutiliza fotos."""
import html
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

FEEDS = {
    "Singletracks": "https://www.singletracks.com/feed/",
    "BikeRumor MTB": "https://bikerumor.com/bike-types/mountain-bike/feed/",
    "E-Mountainbike": "https://ebike-mtb.com/en/feed/",
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php",
}
DESTINO = Path("data/fuentes_editoriales.json")
DIAS = 7
MAX_CANDIDATAS = 30
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"


class TextoHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []
        self.omitir = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.omitir += 1
        if tag in ("p", "h1", "h2", "h3", "li", "br"):
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.omitir = max(0, self.omitir - 1)
        if tag in ("p", "h1", "h2", "h3", "li"):
            self.partes.append("\n")

    def handle_data(self, data):
        if not self.omitir:
            self.partes.append(data)


def limpiar(texto):
    parser = TextoHTML()
    parser.feed(str(texto or ""))
    lineas = [re.sub(r"\s+", " ", x).strip() for x in "".join(parser.partes).splitlines()]
    return "\n".join(x for x in lineas if x)[:14000]


def fecha_publicacion(item):
    raw = (item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
    try:
        fecha = parsedate_to_datetime(raw)
        return fecha.replace(tzinfo=timezone.utc) if fecha.tzinfo is None else fecha.astimezone(timezone.utc)
    except (ValueError, TypeError):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None


def normalizar_url(url):
    try:
        u = urlsplit(url.strip())
        if u.scheme != "https" or not u.hostname:
            return ""
        return urlunsplit((u.scheme, u.netloc.lower(), u.path.rstrip("/"), "", ""))
    except ValueError:
        return ""


def contexto(item):
    opciones = [
        item.findtext(CONTENT_NS),
        item.findtext("description"),
        item.findtext("{http://www.w3.org/2005/Atom}content"),
        item.findtext("{http://www.w3.org/2005/Atom}summary"),
    ]
    return max((limpiar(x) for x in opciones if x), key=len, default="")


def imagen_de_noticia(item, url):
    """Priorizar la imagen que el propio artículo distribuye en RSS."""
    candidates = []
    for nodo in item.iter():
        etiqueta = nodo.tag.split("}")[-1].lower()
        tipo = (nodo.attrib.get("type") or "").lower()
        if etiqueta in ("thumbnail", "content", "enclosure"):
            if etiqueta != "enclosure" or tipo.startswith("image/") or nodo.attrib.get("url", "").lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                candidates.append(nodo.attrib.get("url") or "")
    if not candidates:
        for field in (item.findtext("description") or "", item.findtext(CONTENT_NS) or ""):
            m = re.search(r"""<img[^>]+(?:src|data-src)=["']([^"']+)""", field, re.I)
            if m:
                candidates.append(html.unescape(m.group(1)))
                break
    for candidate in candidates:
        target = urljoin(url, html.unescape(candidate))
        parts = urlsplit(target)
        if parts.scheme == "https" and parts.hostname:
            return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return ""


def extraer(feed, nombre, corte, ahora):
    req = Request(feed, headers={"User-Agent": "DescensoEditorialBot/1.0 (+https://descenso.cl)"})
    with urlopen(req, timeout=18) as respuesta:
        datos = respuesta.read(2_500_000)
    raiz = ET.fromstring(datos)
    items = raiz.findall(".//item")
    if not items:
        items = raiz.findall("{http://www.w3.org/2005/Atom}entry")
    encontrados = []
    for item in items[:45]:
        titulo = limpiar(item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title"))
        enlace = (item.findtext("link") or "").strip()
        if not enlace:
            enlace = next((el.attrib.get("href", "") for el in item.findall("{http://www.w3.org/2005/Atom}link") if el.attrib.get("rel", "alternate") == "alternate"), "")
        url = normalizar_url(enlace)
        fecha = fecha_publicacion(item)
        if not titulo or not url or not fecha or not corte <= fecha <= ahora:
            continue
        cuerpo = contexto(item)
        encontrados.append({
            "fuente": nombre,
            "titulo": titulo,
            "url": url,
            "fecha": fecha.isoformat(),
            "contexto": cuerpo,
            "palabras": len(cuerpo.split()),
            "imagen": imagen_de_noticia(item, url),
            "image_credit": f"{nombre} / fuente original (fotógrafo por confirmar)",
            "imagen_pendiente_revision": True,
        })
    return encontrados


def main():
    ahora = datetime.now(timezone.utc)
    corte = ahora - timedelta(days=DIAS)
    vistas = set()
    todas = []
    for nombre, url in FEEDS.items():
        try:
            items = extraer(url, nombre, corte, ahora)
            print(f"{nombre}: {len(items)} artículos recientes; con contexto suficiente: {sum(n['palabras'] >= 120 for n in items)}", flush=True)
            for noticia in items:
                if noticia["url"] not in vistas:
                    vistas.add(noticia["url"])
                    todas.append(noticia)
        except (OSError, ET.ParseError, ValueError) as exc:
            print(f"{nombre}: error de lectura ({type(exc).__name__}: {exc})", flush=True)
    todas.sort(key=lambda n: (n["palabras"] >= 120, n["fecha"]), reverse=True)
    seleccion = todas[:MAX_CANDIDATAS]
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps({"actualizado": ahora.isoformat(), "noticias": seleccion}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Candidatas: {len(seleccion)}; con contexto >=120 palabras: {sum(n['palabras'] >= 120 for n in seleccion)}", flush=True)


if __name__ == "__main__":
    main()
