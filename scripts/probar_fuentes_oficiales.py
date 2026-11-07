"""Diagnóstico independiente de fuentes oficiales para Descenso.cl.

No modifica datos, borradores ni noticias publicadas.
Ejecutar: python scripts/probar_fuentes_oficiales.py
"""
import html
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

FUENTES = {
    "UCI": "https://www.uci.org/",
    "UCI MTB World Series": "https://www.ucimtbworldseries.com/",
    "Red Bull Bike": "https://www.redbull.com/int-en/tags/bike",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DescensoNewsResearch/1.0)"}

class AnalizadorHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.feeds = []
        self.descripcion = ""
        self.titulo = ""
        self._en_titulo = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and "alternate" in a.get("rel", "").lower():
            if any(x in a.get("type", "").lower() for x in ("rss", "atom")):
                self.feeds.append(a.get("href", ""))
        if tag == "meta":
            clave = (a.get("name") or a.get("property") or "").lower()
            if clave in ("description", "og:description") and not self.descripcion:
                self.descripcion = a.get("content", "")
        if tag == "title":
            self._en_titulo = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_titulo = False

    def handle_data(self, data):
        if self._en_titulo:
            self.titulo += data


def obtener(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=18) as respuesta:
        tipo = respuesta.headers.get("Content-Type", "")
        final = respuesta.geturl()
        contenido = respuesta.read(800_000)
    return tipo, final, contenido


def revisar_feed(url):
    tipo, final, contenido = obtener(url)
    raiz = ElementTree.fromstring(contenido)
    entradas = raiz.findall("./channel/item")
    if not entradas:
        entradas = [e for e in raiz.iter() if e.tag.split("}")[-1] == "entry"]
    muestras = []
    for entrada in entradas[:3]:
        titulo = next((e.text for e in entrada if e.tag.split("}")[-1] == "title"), "")
        muestras.append((titulo or "").strip()[:120])
    return {"url": final, "entradas": len(entradas), "titulos_muestra": muestras}


def main():
    print("DIAGNÓSTICO DE FUENTES OFICIALES — DESCENSO.CL", flush=True)
    print("Fecha UTC:", datetime.now(timezone.utc).isoformat(), flush=True)
    print("No se modificará ningún archivo del repositorio.\n", flush=True)
    for nombre, url in FUENTES.items():
        print(f"=== {nombre} ===", flush=True)
        try:
            tipo, final, contenido = obtener(url)
            print("Página:", final, flush=True)
            print("Content-Type:", tipo, flush=True)
            if "html" not in tipo.lower() and b"<html" not in contenido[:1000].lower():
                print("Respuesta no HTML; requiere revisión manual.\n", flush=True)
                continue
            analizador = AnalizadorHTML()
            analizador.feed(contenido.decode("utf-8", errors="replace"))
            print("Título:", html.unescape(analizador.titulo.strip())[:130], flush=True)
            print("Descripción:", html.unescape(analizador.descripcion.strip())[:250], flush=True)
            feeds = sorted(set(urljoin(final, feed) for feed in analizador.feeds if feed))
            print("RSS/Atom declarados:", len(feeds), flush=True)
            for feed in feeds[:5]:
                print("Feed:", feed, flush=True)
                try:
                    print("Resultado:", json.dumps(revisar_feed(feed), ensure_ascii=False), flush=True)
                except (urllib.error.URLError, ElementTree.ParseError, TimeoutError, ValueError) as error:
                    print("Feed no verificable:", type(error).__name__, str(error)[:150], flush=True)
            if not feeds:
                print("Sin RSS/Atom declarado. NO incorporar al buscador todavía.", flush=True)
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            print("No accesible:", type(error).__name__, str(error)[:180], flush=True)
        print(flush=True)
    print("FIN. Este diagnóstico no autoriza copiar artículos ni imágenes.", flush=True)

if __name__ == "__main__":
    main()
