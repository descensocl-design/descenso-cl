#!/usr/bin/env python3
"""Diagnostica texto editorial de una noticia UCI; no guarda ni publica nada."""
import json
import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

URL = 'https://www.ucimtbworldseries.com/news/whoop-uci-mountain-bike-world-series-confirms-2027-calendar'

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.ignore = 0
        self.capture = []
        self.parts = []
        self.scripts = []
        self.jsonld = False
        self.jsonbuf = []
        self.title = ''
        self.intitle = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside', 'form'):
            self.ignore += 1
        if tag == 'script' and a.get('type', '').lower() == 'application/ld+json':
            self.jsonld = True
            self.jsonbuf = []
        if tag == 'title':
            self.intitle = True
        if tag in ('main', 'article'):
            self.depth += 1
        if tag in ('p', 'h1', 'h2', 'h3') and self.depth and not self.ignore:
            self.capture.append([tag, []])

    def handle_data(self, data):
        if self.jsonld:
            self.jsonbuf.append(data)
        if self.intitle:
            self.title += data
        if self.capture and not self.ignore:
            self.capture[-1][1].append(data)

    def handle_endtag(self, tag):
        if self.capture and tag == self.capture[-1][0]:
            _, chunks = self.capture.pop()
            txt = ' '.join(' '.join(chunks).split())
            if len(txt) >= 30:
                self.parts.append(txt)
        if tag in ('main', 'article'):
            self.depth = max(0, self.depth - 1)
        if tag == 'title':
            self.intitle = False
        if tag == 'script' and self.jsonld:
            self.scripts.append(''.join(self.jsonbuf))
            self.jsonld = False
        if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside', 'form'):
            self.ignore = max(0, self.ignore - 1)

def walk_json(obj):
    if isinstance(obj, dict):
        typ = obj.get('@type', '')
        if isinstance(typ, list):
            typ = ' '.join(map(str, typ))
        if 'Article' in str(typ) or 'NewsArticle' in str(typ):
            yield obj
        for v in obj.values():
            yield from walk_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_json(v)

def main():
    assert urlparse(URL).hostname == 'www.ucimtbworldseries.com'
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0 (compatible; DescensoResearch/1.0)'})
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read(2_000_000)
        print('HTTP:', response.status, '| bytes:', len(raw))
    parser = Extractor()
    parser.feed(raw.decode('utf-8', errors='replace'))
    print('Título HTML:', parser.title.strip()[:200])
    print('Párrafos en main/article:', len(parser.parts))
    text = '\n'.join(dict.fromkeys(parser.parts))
    print('Palabras extraídas:', len(text.split()))
    print('MUESTRA DE PÁRRAFOS (máximo 5):')
    for p in list(dict.fromkeys(parser.parts))[:5]:
        print('-', p[:300])
    found = 0
    for script in parser.scripts:
        try:
            data = json.loads(script)
        except json.JSONDecodeError:
            continue
        for article in walk_json(data):
            found += 1
            body = article.get('articleBody', '')
            print('JSON-LD fecha:', article.get('datePublished', 'no disponible'))
            print('JSON-LD articleBody palabras:', len(str(body).split()))
    print('JSON-LD artículos:', found)
    print('RESULTADO:', 'CANDIDATO A REVISIÓN MANUAL' if len(text.split()) >= 180 else 'INSUFICIENTE O ESTRUCTURA NO RECONOCIDA')
    print('Este diagnóstico NO acredita que todo el texto sea editorial ni autoriza republicación.')

if __name__ == '__main__':
    main()
