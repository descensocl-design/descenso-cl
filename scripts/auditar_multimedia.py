#!/usr/bin/env python3
"""Auditoría editorial de fotografías y videos: no inventar contenido."""
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
POSTS=ROOT/"data/posts.json"
OUT=ROOT/"data/revision-multimedia.json"

def main():
    posts=json.loads(POSTS.read_text(encoding="utf-8"))
    report=[]
    for p in posts:
        images=p.get("images") if isinstance(p.get("images"),list) else []
        source=str(p.get("link") or "")
        video=str(p.get("video_embed") or p.get("youtube") or p.get("video_url") or "")
        title=str(p.get("title",""))
        has_source=urlparse(source).scheme=="https"
        is_video_article=any(word in title.lower() for word in ("video:", "video ", "documental"))
        issues=[]
        if not has_source:
            issues.append("No hay enlace a la publicación original: verificar fuente y créditos")
        if p.get("auto_published") and not images and not p.get("media_review"):
            issues.append("Solo portada: comprobar si la noticia original contiene fotografías adicionales")
        if is_video_article and not video:
            issues.append("La noticia anuncia video, pero no tiene reproductor original verificado")
        if not p.get("image"):
            issues.append("Sin fotografía principal verificada")
        report.append({
          "title":title,"source_url":source,"permalink":p.get("permalink",""),
          "photos_registered":int(bool(p.get("image")))+len(images),
          "video_registered":bool(video),
          "source_media_review":p.get("media_review") or None,
          "issues":issues,
          "status":"pendiente" if issues else "sin_pendientes_detectados"
        })
    OUT.write_text(json.dumps({"total":len(report),"pending":sum(bool(p["issues"]) for p in report),"articles":report},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("AUDITORIA MULTIMEDIA:",len(report),"noticias,",sum(bool(p["issues"]) for p in report),"por revisar")
if __name__=="__main__":main()
