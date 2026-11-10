#!/usr/bin/env python3
"""Produce hasta cinco borradores editoriales pendientes de aprobación humana."""
import html
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

CANDIDATAS = Path("data/fuentes_editoriales.json")
DESTINO = Path("data/borradores-ia")
POSTS = Path("data/posts.json")
MAX_DIARIO = 5
MODELO = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")


def slug(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(x for x in texto if not unicodedata.combining(x))
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:70]


def clasificar(titulo):
    texto = titulo.lower()
    if re.search(r"\b(downhill|dh|world cup|hardline)\b", texto):
        return "Downhill"
    if "enduro" in texto:
        return "Enduro"
    if "freeride" in texto or "rampage" in texto:
        return "Freeride"
    if re.search(r"\b(xc|xco|cross.country)\b", texto):
        return "XC"
    return "Mundo"


def generar(noticia, clave):
    instrucciones = (
        "Eres periodista de Descenso.cl, medio de mountain bike latinoamericano. "
        "Produce una noticia ORIGINAL en español, no una traducción del texto ajeno. "
        "Utiliza EXCLUSIVAMENTE hechos contenidos en la fuente suministrada. "
        "No inventes precios, fechas, cifras, citas, pruebas propias ni conclusiones técnicas. "
        "No atribuyas experiencias de primera mano a Descenso. No copies frases completas. "
        "Si hay pocos datos o el tema es una promoción, devuelve JSON {\"insuficiente\":true}. "
        "Responde SOLO JSON válido con keys: title (titular informativo), excerpt (bajada de 100-220 caracteres), "
        "sections (lista de al menos 2 objetos: cada uno con heading y paragraphs, lista de párrafos originales). "
        "Debe haber al menos 4 párrafos sustanciales en total, dos subtítulos y al menos 170 palabras en el cuerpo. "
        "Prioriza hechos y contexto comprobables; no rellenes con generalidades. "
        "Diferencia anuncios de resultados o hechos confirmados. "
        "Recuerda que el texto será un borrador sujeto a comprobación editorial.\n\n"
        f"FUENTE: {noticia['fuente']}\nURL: {noticia['url']}\n"
        f"TÍTULO: {noticia['titulo']}\nCONTENIDO DISPONIBLE:\n{noticia['contexto'][:10500]}"
    )
    payload = {
        "contents": [{"parts": [{"text": instrucciones}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 3200,
            "responseMimeType": "application/json",
        },
    }
    req = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": clave},
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as respuesta:
            result = json.load(respuesta)
        partes = (result.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        salida = json.loads("".join(p.get("text", "") for p in partes))
    except (HTTPError, URLError, TimeoutError, ValueError, IndexError, KeyError) as exc:
        print(f"ERROR GEMINI {noticia['titulo']}: {type(exc).__name__}: {exc}", flush=True)
        return None
    if not isinstance(salida, dict) or salida.get("insuficiente"):
        return None
    title, excerpt, sections = salida.get("title"), salida.get("excerpt"), salida.get("sections")
    if not isinstance(title, str) or not isinstance(excerpt, str) or not isinstance(sections, list):
        return None
    if not 12 <= len(title.strip()) <= 170 or not 70 <= len(excerpt.strip()) <= 230:
        return None
    parrafos = []
    for sec in sections:
        if not isinstance(sec, dict) or not isinstance(sec.get("heading"), str) or not isinstance(sec.get("paragraphs"), list):
            return None
        if not sec["heading"].strip():
            return None
        if not all(isinstance(x, str) and len(x.split()) >= 15 for x in sec["paragraphs"]):
            return None
        parrafos.extend(sec["paragraphs"])
    if len(sections) < 2 or len(parrafos) < 4 or sum(len(p.split()) for p in parrafos) < 170:
        return None
    return {"title": title.strip(), "excerpt": excerpt.strip(), "sections": sections}


def main():
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave:
        raise SystemExit("Falta GEMINI_API_KEY; no se generaron borradores.")
    noticias = json.loads(CANDIDATAS.read_text(encoding="utf-8")).get("noticias", [])
    DESTINO.mkdir(parents=True, exist_ok=True)
    existentes = set()
    for archivo in DESTINO.glob("*.md"):
        match = re.search(r"^source_url:\s*(.+)$", archivo.read_text(encoding="utf-8"), re.M)
        if match:
            existentes.add(match.group(1).strip().strip('"'))
    if POSTS.exists():
        for p in json.loads(POSTS.read_text(encoding="utf-8")):
            if isinstance(p, dict) and p.get("link"):
                existentes.add(str(p["link"]))
    hoy = datetime.now(ZoneInfo("America/Santiago")).date().isoformat()
    nuevos = 0
    for n in noticias:
        if nuevos >= MAX_DIARIO:
            break
        if n.get("palabras", 0) < 120 or n.get("url") in existentes:
            continue
        resultado = generar(n, clave)
        if resultado is None:
            print(f"Sin borrador apto: {n.get('titulo')}", flush=True)
            continue
        titulo = resultado["title"]
        archivo = DESTINO / f"{hoy}-{slug(titulo)}.md"
        if archivo.exists():
            continue
        cabecera = {
            "title": titulo,
            "date": datetime.now(ZoneInfo("America/Santiago")).isoformat(timespec="seconds"),
            "category": clasificar(n["titulo"]),
            "description": resultado["excerpt"],
            "image": "",
            "image_candidate": n.get("imagen", ""),
            "image_credit": n.get("image_credit", f"{n['fuente']} / fuente original"),
            "source_url": n["url"],
            "source_name": n["fuente"],
            "image_pending_review": True,
            "editorial_approved": False,
        }
        lineas = ["---"] + [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in cabecera.items()] + ["---", "", f"**{resultado['excerpt']}**", ""]
        for seccion in resultado["sections"]:
            lineas.extend([f"## {seccion['heading'].strip()}", ""])
            for parrafo in seccion["paragraphs"]:
                lineas.extend([parrafo.strip(), ""])
        lineas.extend([f"**Fuente:** [{n['fuente']}]({n['url']}).", "", f"**Fotografía candidata:** {n.get('imagen') or 'No identificada'}", f"**Crédito:** {n.get('image_credit', n['fuente'])}.", "", "**Revisión editorial pendiente:** confirmar datos, autoría, derechos de imagen y aprobar antes de mover a data/noticias/.", ""])
        archivo.write_text("\n".join(lineas), encoding="utf-8")
        existentes.add(n["url"])
        nuevos += 1
        print(f"BORRADOR: {archivo}", flush=True)
    print(f"Borradores nuevos: {nuevos}. No se modificó ninguna noticia publicada.", flush=True)
    if nuevos == 0:
        raise SystemExit("SIN BORRADORES: revisar disponibilidad de RSS, material suficiente y respuesta de Gemini.")


if __name__ == "__main__":
    main()
