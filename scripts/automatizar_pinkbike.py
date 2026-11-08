#!/usr/bin/env python3
"""Genera hasta cinco breves diarios de Pinkbike usando su RSS y Gemini.

Por defecto simula. Con --publicar agrega notas a data/posts.json.
No descarga ni reutiliza imágenes de terceros.
"""
import argparse
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

CANDIDATAS = Path("data/noticias_candidatas.json")
POSTS = Path("data/posts.json")
MAX_DIARIO = 5
ZONA = ZoneInfo("America/Santiago")
MODELO = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")


def normalizar_url(url):
    try:
        p = urlsplit(str(url).strip())
        if p.scheme != "https" or p.hostname not in ("www.pinkbike.com", "pinkbike.com"):
            return ""
        return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", ""))
    except ValueError:
        return ""


def limpiar(texto):
    texto = re.sub(r"<[^>]+>", " ", str(texto or ""))
    return re.sub(r"\\s+", " ", html.unescape(texto)).strip()


def contexto_rss(noticia):
    titulo = limpiar(noticia.get("titulo"))
    descripcion = limpiar(noticia.get("descripcion") or noticia.get("contexto_rss"))
    return "\\n".join(p for p in (titulo, descripcion) if p)


def redactar_breve(noticia):
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave:
        return None, "falta GEMINI_API_KEY"
    fuente = contexto_rss(noticia)
    instrucciones = (
        "Eres redactor de Descenso.cl, medio chileno de mountain bike. "
        "Escribe un breve periodístico original en español, de 20 a 75 palabras, "
        "basado EXCLUSIVAMENTE en el título y descripción RSS proporcionados. "
        "No inventes nombres, cifras, fechas, declaraciones, resultados ni contexto. "
        "Si la información es escasa, escribe menos, sin relleno. "
        "No incluyas titular, enlaces, créditos, hashtags ni Markdown. "
        "No afirmes haber leído el artículo completo. "
        "Si no es posible redactar una oración factual, responde SIN_DATOS.\\n\\n"
        "RSS:\\n" + fuente
    )
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + MODELO + ":generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": instrucciones}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 350},
    }
    req = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": clave},
        method="POST",
    )
    try:
        with urlopen(req, timeout=45) as respuesta:
            datos = json.load(respuesta)
        candidatos = datos.get("candidates") or []
        partes = candidatos[0].get("content", {}).get("parts", []) if candidatos else []
        texto = "\\n".join(
            p.get("text", "") for p in partes if isinstance(p, dict)
        ).strip()
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
        return None, f"error de Gemini: {type(exc).__name__}: {exc}"
    if not texto or "SIN_DATOS" in texto:
        return None, "Gemini no pudo redactar con los datos disponibles"
    texto = texto.strip().strip('"')
    if re.search(r"(?im)^\\s*(#|---|title:|source_url:)", texto):
        return None, "Gemini devolvió un formato inesperado"
    palabras = len(texto.split())
    if not 12 <= palabras <= 100:
        return None, f"longitud no válida: {palabras} palabras"
    return texto, None


def categoria(noticia):
    texto = contexto_rss(noticia).lower()
    if re.search(r"\\b(downhill|dh|world cup|hardline)\\b", texto):
        return "Downhill"
    if "enduro" in texto:
        return "Enduro"
    if "freeride" in texto:
        return "Freeride"
    if re.search(r"\\b(xc|xco|cross.country)\\b", texto):
        return "XC"
    return "Mundo"


def preparar(noticia, hoy):
    if not isinstance(noticia, dict) or noticia.get("fuente") != "Pinkbike":
        return None, "fuente no admitida"
    url = normalizar_url(noticia.get("url", ""))
    if not url:
        return None, "URL de Pinkbike inválida"
    comentarios = noticia.get("comentarios")
    if type(comentarios) is not int or comentarios < 0:
        return None, "sin número fiable de comentarios"
    titulo = limpiar(noticia.get("titulo"))
    if len(titulo) < 10:
        return None, "título insuficiente"
    if len(contexto_rss(noticia).split()) < 5:
        return None, "RSS sin información suficiente"
    texto, error = redactar_breve(noticia)
    if error:
        return None, error
    parrafos = [p.strip() for p in re.split(r"\\n\\s*\\n", texto) if p.strip()]
    resumen = " ".join(parrafos)[:220]
    return {
        "title": titulo,
        "date": hoy,
        "category": categoria(noticia),
        "excerpt": resumen,
        "image": "",
        "youtube": "",
        "body": parrafos,
        "link": url,
        "auto_published": True,
        "source_name": "Pinkbike",
        "source_comments_at_selection": comentarios,
    }, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publicar", action="store_true",
        help="Agregar notas a posts.json; sin esta opción solo simula",
    )
    args = parser.parse_args()
    if not CANDIDATAS.exists() or not POSTS.exists():
        raise SystemExit("ERROR: faltan noticias_candidatas.json o posts.json")
    datos = json.loads(CANDIDATAS.read_text(encoding="utf-8"))
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if not isinstance(posts, list) or not isinstance(datos, dict) or not isinstance(datos.get("noticias"), list):
        raise SystemExit("ERROR: formato JSON inesperado")
    hoy = datetime.now(ZONA).date().isoformat()
    usados = {
        normalizar_url(p.get("link", ""))
        for p in posts if isinstance(p, dict)
    }
    usados.discard("")
    publicados = sum(
        1 for p in posts
        if isinstance(p, dict)
        and p.get("date") == hoy
        and p.get("auto_published") is True
        and p.get("source_name") == "Pinkbike"
    )
    cupos = max(0, MAX_DIARIO - publicados)
    noticias = sorted(
        (n for n in datos["noticias"] if isinstance(n, dict)),
        key=lambda n: n.get("comentarios")
        if type(n.get("comentarios")) is int else -1,
        reverse=True,
    )
    aceptadas = []
    for noticia in noticias:
        if len(aceptadas) >= cupos:
            break
        url = normalizar_url(noticia.get("url", ""))
        if url and url in usados:
            print(f'OMITIDA duplicada: {noticia.get("titulo", "")}', flush=True)
            continue
        nota, motivo = preparar(noticia, hoy)
        if motivo:
            print(f'OMITIDA {noticia.get("titulo", "")}: {motivo}', flush=True)
            continue
        aceptadas.append(nota)
        usados.add(url)
        print(
            f'APTA {nota["title"]} | comentarios: '
            f'{nota["source_comments_at_selection"]}',
            flush=True,
        )
    print(
        f'Modo: {"PUBLICAR" if args.publicar else "SIMULAR"}; '
        f'cupos: {cupos}; aptas: {len(aceptadas)}',
        flush=True,
    )
    if args.publicar and aceptadas:
        temporal = POSTS.with_suffix(".json.tmp")
        temporal.write_text(
            json.dumps(aceptadas + posts, ensure_ascii=False, indent=2) + "\\n",
            encoding="utf-8",
        )
        temporal.replace(POSTS)
        print(f"posts.json actualizado: {len(aceptadas)} publicaciones", flush=True)
    else:
        print("posts.json sin modificaciones", flush=True)


if __name__ == "__main__":
    main()
