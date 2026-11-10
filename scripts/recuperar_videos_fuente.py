#!/usr/bin/env python3
"""Recupera SOLO reproductores embebidos por la publicación original."""
import html, json, re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.error import HTTPError, URLError

POSTS = Path('data/posts.json')
ALLOWED = {'www.youtube.com','youtube.com','youtube-nocookie.com','www.youtube-nocookie.com','youtu.be','vimeo.com','www.vimeo.com','player.vimeo.com','www.pinkbike.com','pinkbike.com'}

def embed_url(raw, base):
    url = urljoin(base, html.unescape(raw or '').strip())
    u = urlparse(url)
    if u.scheme != 'https' or u.username or u.password or u.hostname not in ALLOWED:
        return ''
    host = u.hostname
    if host in ('youtube.com','www.youtube.com','youtube-nocookie.com','www.youtube-nocookie.com','youtu.be'):
        vid = parse_qs(u.query).get('v',[''])[0]
        if host == 'youtu.be': vid = u.path.strip('/')
        if not vid:
            m = re.match(r'^/(?:embed|shorts|live)/([\w-]{11})(?:/|$)',u.path)
            vid = m.group(1) if m else ''
        return 'https://www.youtube-nocookie.com/embed/'+vid if re.fullmatch(r'[\w-]{11}',vid) else ''
    if host in ('vimeo.com','www.vimeo.com','player.vimeo.com'):
        m = re.fullmatch(r'/(?:video/)?(\d+)/?',u.path)
        return 'https://player.vimeo.com/video/'+m.group(1) if m else ''
    # Pinkbike: permitir SOLO un iframe de reproductor incluido expresamente en el artículo.
    if host in ('www.pinkbike.com','pinkbike.com') and re.match(r'^/(?:video|embed)/',u.path):
        return url
    return ''

class Frames(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls=[]
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'iframe':
            for key in ('src','data-src'):
                if values.get(key): self.urls.append(values[key])
        # Solo reproductores declarados explícitamente por la página original.
        if tag == 'meta' and values.get('property','').lower() in ('og:video:url','og:video:secure_url','twitter:player'):
            if values.get('content'): self.urls.append(values['content'])

def main():
    posts = json.loads(POSTS.read_text(encoding='utf-8'))
    changed=0
    for post in posts:
        if not isinstance(post,dict) or not post.get('auto_published') or post.get('video_embed'): continue
        source=post.get('link','')
        u=urlparse(source)
        if u.scheme!='https' or u.hostname not in ('www.pinkbike.com','pinkbike.com','www.singletracks.com','singletracks.com','bikerumor.com','www.bikerumor.com','ebike-mtb.com'):
            continue
        try:
            req=Request(source,headers={'User-Agent':'Mozilla/5.0 (compatible; DescensoMediaBot/1.0)'})
            with urlopen(req,timeout=16) as resp:
                if 'text/html' not in resp.headers.get('content-type','').lower(): continue
                page=resp.read(2500000).decode('utf-8','replace')
        except (HTTPError,URLError,OSError,TimeoutError,ValueError) as e:
            print('No se pudo abrir fuente:',source,type(e).__name__)
            continue
        parsed=Frames();parsed.feed(page)
        for raw in parsed.urls:
            video=embed_url(raw,source)
            if video:
                post['video_embed']=video
                changed+=1
                print('Video original insertable:',post['title'],video)
                break
    if changed:
        POSTS.write_text(json.dumps(posts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Reproductores originales recuperados:',changed)

if __name__ == '__main__':
    main()
