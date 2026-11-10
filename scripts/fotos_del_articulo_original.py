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
            print("Fuente inaccesible:",post.get("title"),str(e)[:140],flush=True);continue
        soup=BeautifulSoup(page,"html.parser")
        # Un artículo de Pinkbike contiene texto significativo; detectar el cuerpo por
        # cantidad de párrafos, evitando el resto de la página (recomendaciones, comentarios).
        roots=[]
        for selector in ("[itemprop='articleBody']","#article-content",".article-content",".news-article-content",".blog-section",".blog-content",".news-content","article"):
            roots.extend(soup.select(selector))
        for paragraph in soup.find_all("p"):
            if len(paragraph.get_text(" ",strip=True))<120:continue
            for parent in list(paragraph.parents)[:5]:
                if parent.name in ("body","html"):break
                if len(parent.find_all("p"))>=3:roots.append(parent)
        dedup=[];seen_roots=set()
        for root in roots:
            if id(root) not in seen_roots:
                seen_roots.add(id(root)); dedup.append(root)
        ranked=[]
        for root in dedup:
            bodylen=sum(len(p.get_text(" ",strip=True)) for p in root.find_all("p"))
            pictures=photo_candidates(root,link)
            if bodylen>=650 and pictures:
                ranked.append((len(pictures),min(bodylen,20000),root))
        if not ranked:
            # Pinkbike puede colocar fotografías en bloques multimedia que no
            # utilizan etiquetas img, pero solamente extraemos enlaces dentro
            # de la región editorial, nunca de artículos recomendados.
            start = re.search(r'<(?:iframe|div)[^>]*(?:youtube|video-player|video-container)', page, re.I)
            end_marker = re.search(r'(?:Posted In:|Author Info:|Must Read This Week|id=["\x27]comments)', page, re.I)
            if start and end_marker and end_marker.start() > start.start():
                fragment = page[start.start():end_marker.start()]
                raw_links = re.findall(r"https?:(?:\\/\\/|//)[^\x22\x27\s<>]+", fragment)
                recovered = []
                for raw in raw_links:
                    raw = raw.replace("\\/", "/").replace("&amp;", "&")
                    original = valid_image(raw, link)
                    if original: recovered.append(original)
                unique = []
                keys = set()
                for url in recovered:
                    m = re.search(r"p\d+pb(\d+)", urlsplit(url).path)
                    key = m.group(1) if m else urlsplit(url).path
                    if key not in keys:
                        keys.add(key)
                        unique.append(url)
                cover = post.get("image", "")
                cm = re.search(r"p\d+pb(\d+)", cover)
                coverkey = cm.group(1) if cm else urlsplit(cover).path
                additional = []
                for url in unique:
                    m = re.search(r"p\d+pb(\d+)", url)
                    key = m.group(1) if m else urlsplit(url).path
                    if key != coverkey: additional.append(url)
                additional = additional[:24]
                if additional:
                    post["images"] = additional
                    post["image_source_url"] = link
                    count += 1
                    print("FOTOS DEL ARTÍCULO (multimedia):", post.get("title"), len(additional), flush=True)
                    continue
            print("Sin cuerpo de fotos detectable:", post.get("title"), "candidatos", len(roots), flush=True)
            continue
        ranked.sort(key=lambda x:(x[0],x[1]),reverse=True)
        root=ranked[0][2]
        # Descartar imágenes fuera del cuerpo incluso cuando un contenedor es muy grande:
        # utilizar la zona editorial anterior al pie del artículo/comentarios.
        for selector in (".comments", "#comments", ".comment-list", ".sidebar", ".related-articles", ".most-read"):
            for el in root.select(selector): el.decompose()
        found=photo_candidates(root,link)
        images=[];ids=set()
        for u in found:
            m=re.search(r"p\d+pb(\d+)",urlsplit(u).path)
            identity=m.group(1) if m else urlsplit(u).path
            if identity in ids:continue
            ids.add(identity);images.append(u)
        if not images:continue
        current=post.get("image") or ""
        m=re.search(r"p\d+pb(\d+)",urlsplit(current).path)
        cover_id=m.group(1) if m else urlsplit(current).path
        additional=[u for u in images if (re.search(r"p\d+pb(\d+)",urlsplit(u).path).group(1) if re.search(r"p\d+pb(\d+)",urlsplit(u).path) else urlsplit(u).path)!=cover_id]
        additional=additional[:24]
        if additional and additional!=post.get("images",[]):
            post["images"]=additional
            post["image_source_url"]=link
            count+=1
            print("FOTOS ORIGINALES:",post.get("title"),"nuevas:",len(additional),flush=True)
    if count:
        POSTS.write_text(json.dumps(posts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Noticias con fotografías adicionales actualizadas:",count)

if __name__=="__main__":main()
