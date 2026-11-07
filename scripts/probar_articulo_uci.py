#!/usr/bin/env python3
"""Diagnóstico de contenido editorial UCI. Solo lectura, no guarda ni publica."""
import json
import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

URL = 'https://www.ucimtbworldseries.com/news/whoop-uci-mountain-bike-world-series-confirms-2027-calendar'

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.blocks = []
        self.active = []
        self.title = ''
        self.title_depth = 0
        self.json_scripts = []
        self.json_depth = None
        self.json_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append((tag, attrs))
        if tag == 'title':
            self.title_depth = len(self.stack)
        if tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json':
            self.json_depth = len(self.stack)
            self.json_parts = []
        if tag in ('p', 'h1', 'h2', 'h3'):
            self.active.append({'tag': tag, 'depth': len(self.stack), 'parts': [],
                                'ancestors': list(self.stack[:-1])})

    def handle_data(self, data):
        if self.title_depth:
            self.title += data
        if self.json_depth is not None:
            self.json_parts.append(data)
        if self.active:
            for block in self.active:
                block['parts'].append(data)

    def handle_endtag(self, tag):
        if not self.stack:
            return
        # Close blocks by their recorded nesting depth, tolerating malformed HTML.
        depth = len(self.stack)
        for block in self.active[:]:
            if block['depth'] == depth and block['tag'] == tag:
                txt = ' '.join(''.join(block['parts']).split())
                if len(txt) >= 30:
                    self.blocks.append((txt, block['tag'], block['ancestors']))
                self.active.remove(block)
        if self.title_depth == depth and tag == 'title':
            self.title_depth = 0
        if self.json_depth == depth and tag == 'script':
            self.json_scripts.append(''.join(self.json_parts))
            self.json_depth = None
        # Most pages have well-formed nesting; ignore stray closing tags.
        if self.stack[-1][0] == tag:
            self.stack.pop()
        else:
            for i in range(len(self.stack)-1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break

def ignored(ancestors):
    for tag, attrs in ancestors:
        if tag in ('nav', 'header', 'footer', 'aside', 'script', 'style', 'form'):
            return True
        marker = ' '.join((attrs.get('class', ''), attrs.get('id', ''), attrs.get('role', ''))).lower()
        if any(word in marker for word in ('cookie', 'breadcrumb', 'newsletter', 'related', 'recommend', 'social', 'share', 'navigation', 'menu')):
            return True
    return False

def parent_signature(ancestors):
    for tag, attrs in reversed(ancestors):
        if tag in ('section', 'article', 'main', 'div'):
            cls = attrs.get('class', '')
            return f'{tag}#{attrs.get("id", "")}.{str(cls)[:90]}'
    return '(sin contenedor)'

def find_articles(obj):
    if isinstance(obj, dict):
        typ = obj.get('@type', '')
        if 'Article' in str(typ):
            yield obj
        for value in obj.values():
            yield from find_articles(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from find_articles(value)

def main():
    if urlparse(URL).hostname != 'www.ucimtbworldseries.com':
        raise SystemExit('Dominio no autorizado')
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0 (compatible; DescensoResearch/1.0)'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read(2_000_000)
        print('HTTP:', resp.status, '| bytes:', len(raw), flush=True)
    parser = Extractor()
    parser.feed(raw.decode('utf-8', errors='replace'))
    print('Título HTML:', parser.title.strip()[:160])
    print('Bloques HTML detectados:', len(parser.blocks))
    candidates = [(t, tag, anc) for t, tag, anc in parser.blocks if not ignored(anc)]
    print('Bloques sin navegación/elementos descartados:', len(candidates))
    # Diagnostic only: these may still contain related stories, not verified article body.
    unique = list(dict.fromkeys((t, tag, parent_signature(anc)) for t, tag, anc in candidates))
    paragraphs = [(t, sig) for t, tag, sig in unique if tag == 'p' and len(t.split()) >= 8]
    print('Párrafos candidatos:', len(paragraphs))
    print('Palabras en párrafos candidatos:', sum(len(t.split()) for t, _ in paragraphs))
    print('MUESTRA DE HASTA 8 PÁRRAFOS (incluye contenedor):')
    for t, sig in paragraphs[:8]:
        print('CONTENEDOR:', sig)
        print('TEXTO:', t[:500])
    articles = []
    for raw_json in parser.json_scripts:
        try:
            articles.extend(find_articles(json.loads(raw_json)))
        except json.JSONDecodeError:
            pass
    print('JSON-LD artículos:', len(articles))
    for a in articles[:3]:
        print('JSON-LD fecha:', a.get('datePublished', 'no disponible'))
        print('JSON-LD cuerpo (palabras):', len(str(a.get('articleBody', '')).split()))
    print('RESULTADO: DIAGNÓSTICO; REQUIERE REVISIÓN MANUAL DE LOS PÁRRAFOS')
    print('No guarda archivos, no modifica borradores y no autoriza reutilizar textos o imágenes.')

if __name__ == '__main__':
    main()
