#!/usr/bin/env python3
"""Evita regresiones del catálogo de Descenso.cl en GitHub Actions."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
posts=json.loads((ROOT/"data/posts.json").read_text(encoding="utf-8"))
by_cover={str(p.get("image")):p for p in posts}
checks=[
 ("Sedona", "30494759", 53, 0),
 ("Matthew Fairbrother", "30488768", 5, 1),
 ("YT Decoy X", "30435456", 17, 0),
 ("Ghost Bikes", "28117509", 0, 0),
 ("Line of the Year", "30277249", 0, 10),
]
fail=[]
for name,cover,nphotos,nvideos in checks:
    post=next((p for p in posts if cover in str(p.get("image",""))),None)
    if not post:
        fail.append(f"{name}: falta publicación")
        continue
    count=len(post.get("images") or [])
    videos=int(bool(post.get("video_embed") or post.get("youtube")))
    video_collection=post.get("official_video_collection") or {}
    videos+=sum(isinstance(v,dict) and str(v.get("embed","")).startswith("https://www.youtube-nocookie.com/embed/") for v in video_collection.get("entries",[]))
    if count < nphotos:
        fail.append(f"{name}: {count} fotos, mínimo {nphotos}")
    if videos < nvideos:
        fail.append(f"{name}: {videos} videos, mínimo {nvideos}")
    if name=="Ghost Bikes" and ("evita su cierre" not in post.get("title","").lower() or "ghost-bikes-will-continue" not in post.get("link","")):
        fail.append("Ghost Bikes: volvió el titular falso de cierre")
print("Validación editorial:",len(checks),"noticias clave")
if fail:
    raise SystemExit("\n".join(fail))
print("Sin regresiones de noticias, fotos ni videos")
