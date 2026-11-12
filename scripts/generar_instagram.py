#!/usr/bin/env python3
"""Portadas originales para Instagram desde cada noticia de Descenso.cl.
No utiliza ni redistribuye imágenes de terceros.
"""
import json
import re
import unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"assets"/"instagram"
SIZE=(1080,1350)
BG="#101012"
FG="#f4f3f1"
RED="#d71f32"
MUTED="#95959c"

def slugify(s):
    value=unicodedata.normalize("NFD",str(s))
    value="".join(x for x in value if unicodedata.category(x)!="Mn")
    return re.sub(r"[^a-z0-9]+","-",value.lower()).strip("-")[:85] or "noticia"

def identifier(post):
    permalink=str(post.get("permalink") or "")
    if re.fullmatch(r"/noticias/[a-z0-9-]+/",permalink):
        return permalink.strip("/").split("/")[-1]
    return str(post.get("date") or "sin-fecha")+"-"+slugify(post.get("title","noticia"))

def font(sz,bold=False):
    paths=(
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for p in paths:
        try: return ImageFont.truetype(p,sz)
        except OSError: pass
    return ImageFont.load_default()

def wrap(draw,text,ft,maxw):
    words=str(text).split()
    lines=[]
    current=""
    for w in words:
        trial=(current+" "+w).strip()
        if draw.textbbox((0,0),trial,font=ft)[2] > maxw and current:
            lines.append(current)
            current=w
        else: current=trial
    if current:lines.append(current)
    return lines

def draw_card(post):
    im=Image.new("RGB",SIZE,BG)
    d=ImageDraw.Draw(im)
    # Grilla editorial discreta y márgenes generosos.
    for y in range(200,1300,140):
        d.line([(90,y),(990,y)],fill="#1f1f23",width=1)
    d.rectangle((90,92,240,100),fill=RED)
    d.text((90,125),"DESCENSO.CL",font=font(58,True),fill=FG)
    d.text((90,220),str(post.get("category") or "MTB").upper()+"  /  MOUNTAIN BIKE",font=font(24,True),fill=RED)
    title=str(post.get("title") or "").strip()
    selected=(font(70,True),[])
    for size in range(79,41,-3):
        ft=font(size,True)
        lines=wrap(d,title,ft,900)
        lineheight=size+20
        if len(lines)*lineheight <= 740:
            selected=(ft,lines)
            break
    ft,lines=selected
    lineheight=getattr(ft,"size",60)+20
    start=int(680-(len(lines)*lineheight)/2)
    for i,line in enumerate(lines):
        # Text-centered but with consistent editorial margins.
        d.text((90,start+i*lineheight),line,font=ft,fill=FG)
    d.rectangle((90,1093,990,1097),fill=RED)
    d.text((90,1133),"LA HISTORIA COMPLETA",font=font(27,True),fill=FG)
    d.text((90,1194),"DESCENSO.CL",font=font(34,True),fill=FG)
    d.text((90,1284),"DOWNHILL  /  ENDURO  /  FREERIDE",font=font(19),fill=MUTED)
    return im

def main():
    posts=json.loads((ROOT/"data/posts.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True,exist_ok=True)
    names=set()
    for post in posts:
        if not isinstance(post,dict) or not post.get("title"):continue
        name=identifier(post)+".jpg"
        names.add(name)
        draw_card(post).save(OUT/name,format="JPEG",quality=90,optimize=True,subsampling=0)
    # Solo borrar portadas regeneradas que dejaron de corresponder a noticias.
    for old in OUT.glob("*.jpg"):
        if old.name not in names:old.unlink()
    print(f"Portadas de Instagram: {len(names)}")

if __name__=="__main__":
    main()
