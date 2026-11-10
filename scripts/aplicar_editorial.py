#!/usr/bin/env python3
"""Aplica correcciones editoriales inmutables luego de los importadores.

Es deliberadamente la última etapa antes de generar HTML: las fuentes
externas (RSS, Pinkbike, etc.) no pueden borrar galerías ya verificadas.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "data/posts.json"
OVERRIDES = ROOT / "data/editorial-overrides.json"

def main():
    if not OVERRIDES.exists():
        return
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    rules = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    done = 0
    for post in posts:
        key = str(post.get("date", "")) + "|" + str(post.get("image", ""))
        patch = rules.get(key)
        if not patch:
            continue
        post.update({k: v for k, v in patch.items() if v is not None})
        done += 1
        if patch.get("images"):
            print("GALERÍA PROTEGIDA:", post.get("title"), len(post["images"]))
        if patch.get("official_video_collection"):
            print("VIDEOS PROTEGIDOS:", post.get("title"), len(post["official_video_collection"].get("entries", [])))
    if done:
        POSTS.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Rectificaciones editoriales aplicadas:", done)
if __name__ == "__main__":
    main()
