#!/usr/bin/env python3
"""Prepara borradores Markdown para revisión. Nunca publica noticias."""
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from automatizar_pinkbike import redactar, categoria, normalizar_url, limpiar

ORIGEN = Path("data/noticias_ampliadas.json")
DESTINO = Path("data/borradores-ia")
MAX_BORRADORES = 5


def slug(texto):
    import unicodedata
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:75]


def main():
    datos = json.loads(ORIGEN.read_text(encoding="utf-8"))
    DESTINO.mkdir(parents=True, exist_ok=True)
    existentes = set()
    for archivo in DESTINO.glob("*.md"):
        contenido = archivo.read_text(encoding="utf-8")
        m = re.search(r"^source_url:\s*(.+)$", contenido, re.M)
        if m:
            existentes.add(m.group(1).strip().strip('"'))
    hoy = datetime.now(ZoneInfo("America/Santiago")).date().isoformat()
    creados = 0
    candidatas = sorted(datos.get("noticias", []), key=lambda n: n.get("comentarios") if isinstance(n.get("comentarios"), int) else -1, reverse=True)
    for noticia in candidatas:
        if creados >= MAX_BORRADORES:
            break
        url = normalizar_url(noticia.get("url", ""))
        if not url or url in existentes:
            continue
        resultado, error = redactar(noticia)
        if error:
            print(f"OMITIDA: {limpiar(noticia.get('titulo'))}: {error}")
            continue
        titulo = resultado["title"]
        nombre = f"{hoy}-{slug(titulo)}.md"
        archivo = DESTINO / nombre
        if archivo.exists():
            continue
        imagen_candidata = str(noticia.get("imagen") or "").strip()
        credito = str(noticia.get("credito") or "").strip()
        fotografo = str(noticia.get("fotografo") or "").strip()
        # image vacío deliberadamente: ninguna imagen externa se publica sin autorización.
        cabecera = {
            "title": titulo,
            "date": hoy + "T12:00:00-03:00",
            "category": categoria(noticia),
            "source_url": url,
            "image": "",
            "image_candidate": imagen_candidata,
            "image_credit": credito,
            "photographer": fotografo,
            "image_pending_review": True,
            "editorial_approved": False,
        }
        # JSON strings son también escalares YAML válidos.
        lineas = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in cabecera.items()] + ["---", "", f"**{resultado['excerpt']}**", ""]
        lineas += [p + "\n" for p in resultado["body"]]
        lineas += [f"**Fuente:** {url}", "", "**Estado:** Borrador sin verificar. Revisar datos, completar contexto, añadir subtítulos y autorizar fotografía antes de publicar.", ""]
        archivo.write_text("\n".join(lineas), encoding="utf-8")
        existentes.add(url)
        creados += 1
        print(f"BORRADOR: {archivo}")
    print(f"Borradores nuevos: {creados}. No se modificó data/noticias ni data/posts.json.")


if __name__ == "__main__":
    main()
