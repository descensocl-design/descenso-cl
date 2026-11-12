#!/usr/bin/env python3
"""Prepara borradores editoriales de Instagram sin publicar ni autorizar imágenes ajenas.

Se ejecuta al sincronizar las noticias y produce un catálogo de propuestas.
Las correcciones del editor y los estados de publicación se guardan aparte en D1.
"""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "posts.json"
TARGET = ROOT / "data" / "instagram-drafts.json"


def slugify(value):
    chars = unicodedata.normalize("NFD", str(value))
    chars = "".join(char for char in chars if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", chars.lower()).strip("-")[:85] or "noticia"


def identifier(post):
    permalink = str(post.get("permalink") or "")
    if re.fullmatch(r"/noticias/[a-z0-9-]+/", permalink):
        return permalink.strip("/").split("/")[-1]
    return str(post.get("date") or "") + "-" + slugify(post.get("title", ""))


def caption(post):
    category = str(post.get("category") or "Mountain Bike").upper()
    tag = "Downhill" if category == "DOWNHILL" else ("Enduro" if category == "ENDURO" else "MTB")
    return "\n".join([
        str(post.get("title") or "").strip(), "",
        str(post.get("excerpt") or "").strip(), "",
        "Lee la noticia completa en DESCENSO.CL. Enlace en la biografía.", "",
        "#DescensoCL #MountainBike #" + tag,
    ])[:2200]


def prepare(posts):
    drafts = []
    seen = set()
    for post in posts:
        if not isinstance(post, dict) or not post.get("title") or not post.get("date"):
            continue
        slug = identifier(post)
        if slug in seen or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}-[a-z0-9-]{4,145}", slug):
            continue
        seen.add(slug)
        drafts.append({
            "slug": slug,
            "title": str(post["title"]).strip(),
            "date": str(post["date"])[:10],
            "category": str(post.get("category") or "Mountain Bike"),
            "permalink": str(post.get("permalink") or "/noticias/" + slug + "/"),
            "caption": caption(post),
            # Imagen propia generada en scripts/generar_instagram.py.
            "image_url": "https://descenso.cl/assets/instagram/" + slug + ".jpg",
        })
    return drafts


def main():
    posts = json.loads(SOURCE.read_text(encoding="utf-8"))
    drafts = prepare(posts)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(drafts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Borradores Instagram preparados (sin publicar): {len(drafts)}")


if __name__ == "__main__":
    main()
