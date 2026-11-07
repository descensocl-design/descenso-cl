"""Diagnóstico de contenido público de UCI MTB World Series; no guarda archivos."""
import json
import re
import urllib.error
import urllib.request
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

BASE = 'https://www.ucimtbworldseries.com'
URLS = [BASE + '/news', BASE + '/news/whoop-uci-mountain-bike-world-series-confirms-2027-calendar']
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; DescensoNewsResearch/1.0)', 'Accept': 'text/html,application/xhtml+xml'}

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_p = False
        self.title = []
        self.paragraphs = []
        self.current = []
        self.links = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag == 'p': self.in_p, self.current = True, []
        if tag == 'a' and a.get('href'):
            href = urljoin(BASE, a['href'])
            if urlsplit(href).netloc == urlsplit(BASE).netloc and '/news/' in urlsplit(href).path:
                self.links.add(href.split('#')[0].split('?')[0])
    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if self.in_p: self.current.append(data)
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'p' and self.in_p:
            text = ' '.join(''.join(self.current).split())
            if len(text) >= 40: self.paragraphs.append(text)
            self.in_p = False

def scan_jsonld(html):
    scripts = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S)
    found = []
    for s in scripts:
        try:
            data = json.loads(unescape(s))
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if isinstance(node, dict):
                    found.append({'type': node.get('@type'), 'headline': node.get('headline'), 'datePublished': node.get('datePublished'), 'articleBody_words': len(str(node.get('articleBody') or '').split())})
        except (ValueError, TypeError): pass
    return found

def main():
    print('PRUEBA EXTRACCIÓN UCI — NO SE MODIFICAN ARCHIVOS', flush=True)
    for url in URLS:
        print('\nURL:', url, flush=True)
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read(2_000_000)
                content_type = resp.headers.get('Content-Type', '')
            html = raw.decode('utf-8', errors='replace')
            p = Extractor(); p.feed(html)
            print('HTTP: 200 | Tipo:', content_type)
            print('Título HTML:', ' '.join(''.join(p.title).split())[:200])
            print('Enlaces de noticias:', len(p.links))
            for link in sorted(p.links)[:5]: print(' -', link)
            print('Párrafos HTML >=40 caracteres:', len(p.paragraphs))
            print('Palabras en párrafos:', sum(len(x.split()) for x in p.paragraphs))
            print('JSON-LD:', json.dumps(scan_jsonld(html)[:5], ensure_ascii=False))
            print('Muestra de texto:', ' '.join(p.paragraphs)[:350])
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print('No accesible:', type(e).__name__, str(e)[:150], flush=True)
    print('\nFIN. Acceso público no implica permiso para reutilizar texto o imágenes.', flush=True)

if __name__ == '__main__':
    main()
