#!/usr/bin/env python3
"""Detecta fotografías insertadas en el cuerpo del artículo ORIGINAL.
Nunca usa búsqueda genérica de imágenes ni material de artículos relacionados.
"""
import json, re, html
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse, urlsplit
from bs4 import BeautifulSoup

POSTS = Path("data/posts.json")
IMAGE_HOSTS = ("pinkbike.org", "pinkbike.com")
ATTRS = ("data-original", "data-full", "data-large", "data-src", "src")

def valid_image(raw, base):
    if not raw: return ""
    url = urljoin(base, html.unescape(str(raw)).strip())
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(IMAGE_HOSTS): return ""
    if not re.search(r"\.(?:jpe?g|png|webp)(?:$|[?#])", parsed.path, re.I): return ""
    lower = parsed.path.lower()
    if any(bad in lower for bad in ("avatar", "flag", "badge", "logo", "smiley", "emoji", "icon", "sprite", "pixel")): return ""
    return url

def photo_candidates(container, base):
    photos = []
    for tag in container.find_all(["img", "a", "source", "picture", "div"]):
        values = []
        if tag.name == "a":
            values.append(tag.get("href"))
        elif tag.name == "source":
            values.extend(x.strip().split(" ")[0] for x in (tag.get("srcset") or "").split(","))
        else:
            values.extend(tag.get(k) for k in ATTRS)
            values.extend(x.strip().split(" ")[0] for x in (tag.get("srcset") or "").split(","))
        # Pinkbike puede colocar fotografías en atributos de elementos contenedores.
        for key in ("data-photo", "data-image", "data-url", "data-fullsize", "data-large-url", "data-fancybox", "data-background-image"):
            if tag.get(key): values.append(tag.get(key))
        for raw in values:
            u = valid_image(raw,base)
            if u:
                photos.append(u)
                break
    return photos

def main():
    posts=json.loads(POSTS.read_text(encoding="utf-8"))
    count=0
    debug=[]
    for post in posts:
        if not isinstance(post,dict) or not post.get("auto_published"): continue
        link=post.get("link") or ""
        host=urlparse(link).hostname
        if host not in ("www.pinkbike.com","pinkbike.com"): continue
        try:
            req=Request(link,headers={"User-Agent":"Mozilla/5.0 (compatible; DescensoPhotoBot/1.1)"})
            with urlopen(req,timeout=20) as resp:
                if "text/html" not in resp.headers.get("content-type","").lower(): continue
                page=resp.read(3500000).decode("utf-8","replace")
        except Exception as e:
            debug.append({"title":post.get("title"),"error":str(e)[:160]})
            print("Fuente inaccesible:",post.get("title"),str(e)[:140],flush=True);continue
        soup=BeautifulSoup(page,"html.parser")
        # Pinkbike publica galerías editoriales como múltiples bloques .blog-section.
        # Cada bloque puede tener una sola fotografía y una leyenda breve; no
        # exigir 650 caracteres, ya que elimina justamente los fotoreportajes.
        comments_start = soup.select_one(".news-comments-container") or soup.select_one("#commenttop")
        before_comments = {id(tag) for tag in comments_start.find_all_previous()} if comments_start else None
        for unwanted in soup.select("script,style,nav,footer,.sidebar,.related-articles,.most-read,.news-comments-container,#commenttop"):
            unwanted.decompose()
        sections = soup.select(".blog-section")
        # Conservar solo las secciones anteriores al área de comentarios.
        # No buscar fotos en toda la página ni en tarjetas recomendadas.
        if sections:
            photos=[]
            for section in sections:
                if before_comments is not None and id(section) not in before_comments:
                    continue
                if section.find_parent(class_="sidebar") or section.find_parent(class_="related-articles"):
                    continue
                photos.extend(photo_candidates(section,link))
        else:
            # Fallback a contenedores de artículo, sin confundir con la portada.
            roots=[]
            for selector in ("[itemprop='articleBody']","#article-content",".article-content",".news-article-content",".blog-content",".news-content","article"):
                roots.extend(soup.select(selector))
            ranked=[]
            for root in roots:
                pictures=photo_candidates(root,link)
                if pictures:
                    ranked.append((len(pictures),root))
            photos=photo_candidates(max(ranked,key=lambda x:x[0])[1],link) if ranked else []
        unique=[];seen=set()
        for photo in photos:
            m=re.search(r"p\d+pb(\d+)",urlsplit(photo).path)
            identifier=m.group(1) if m else urlsplit(photo).path
            if identifier in seen: continue
            seen.add(identifier);unique.append(photo)
        cover=post.get("image") or ""
        m=re.search(r"p\d+pb(\d+)",urlsplit(cover).path)
        cover_id=m.group(1) if m else urlsplit(cover).path
        additional=[]
        for photo in unique:
            m=re.search(r"p\d+pb(\d+)",urlsplit(photo).path)
            identifier=m.group(1) if m else urlsplit(photo).path
            if identifier != cover_id: additional.append(photo)
        additional=additional[:60]
        debug.append({"title":post.get("title"),"sections":len(sections),"photos_found":len(unique),"additional":len(additional)})
        if additional and additional!=post.get("images",[]):
            post["images"]=additional
            post["image_source_url"]=link
            count+=1
            print("FOTOS DEL ARTÍCULO:",post.get("title"),"bloques:",len(sections),"fotos:",len(additional),flush=True)
        else:
            print("Sin fotos nuevas:",post.get("title"),"bloques:",len(sections),"candidatas:",len(unique),flush=True)
    if count:
        POSTS.write_text(json.dumps(posts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path("data/diagnostico-fotos.json").write_text(json.dumps(debug,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Noticias con fotografías adicionales actualizadas:",count)

if __name__=="__main__":main()
