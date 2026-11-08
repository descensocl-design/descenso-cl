import json
import re
import html
import struct
import urllib.request
import xml.etree.ElementTree as ET

from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, urljoin


FUENTES = {
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php"
}

MAX_POR_FUENTE = 50
MAX_HORAS = 72
MAX_CANDIDATAS = 5

# Aceptar imagenes desde 1000 pixeles de ancho
ANCHO_MINIMO = 1000

HISTORIAL = Path("data/noticias_procesadas.json")
CANDIDATAS = Path("data/noticias_candidatas.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DescensoNewsBot/1.0)"
}


def limpiar_texto(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return " ".join(html.unescape(texto).split())


def extraer_contenido_rss(item):
    """Recupera contenido editorial ampliado si el RSS lo incluye.

    No intenta eludir bloqueos de las páginas originales.
    """
    campos = []
    for elemento in item.iter():
        etiqueta = elemento.tag.split("}")[-1].lower()
        espacio = elemento.tag.split("}")[0] if "}" in elemento.tag else ""
        if etiqueta == "encoded" and "content" in espacio:
            campos.append(elemento.text or "")
        elif etiqueta == "description":
            campos.append(elemento.text or "")

    textos = [limpiar_texto(campo) for campo in campos]
    textos = [texto for texto in textos if texto]
    if not textos:
        return ""
    # Se conserva el texto más completo, sin inventar información.
    return max(textos, key=len)[:8000]


def evaluar_contexto(texto):
    """Indicador orientativo; no sustituye verificación editorial."""
    palabras = len(texto.split())
    if palabras >= 180:
        return "amplio"
    if palabras >= 80:
        return "parcial"
    return "insuficiente"


def extraer_numero(texto, patron):
    coincidencia = re.search(
        patron, texto or "", re.IGNORECASE
    )
    if not coincidencia:
        return None
    return int(coincidencia.group(1).replace(",", ""))


def extraer_interacciones(descripcion):
    comentarios = extraer_numero(
        descripcion, r"Comments:\s*([\d,]+)"
    )
    votos = extraer_numero(
        descripcion, r"(?:Likes|Votes):\s*([\d,]+)"
    )
    return comentarios, votos


def convertir_fecha(texto):
    try:
        fecha = parsedate_to_datetime(texto)
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
