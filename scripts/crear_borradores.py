"""Genera borradores MTB en español con Gemini, sin publicarlos automáticamente.

Requiere GEMINI_API_KEY en el entorno para redacción IA. Sin clave, genera ficha.
Solo utiliza datos de RSS y metadatos de noticias_candidatas.json.
"""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

CANDIDATAS = Path('data/noticias_candidatas.json')
HISTORIAL = Path('data/noticias_procesadas.json')
CARPETA_BORRADORES = Path('data/borradores-ia')
CARPETA_PUBLICADAS = Path('data/noticias')
MAX_BORRADORES_DIA = 5
MODELO_GEMINI = os.getenv('GEMINI_MODEL', 'gemini-flash-lite-latest')


def normalizar_url(url):
    partes = urlsplit(str(url or '').strip())
    return urlunsplit((partes.scheme.lower(), partes.netloc.lower(), partes.path.rstrip('/'), '', ''))


def cargar_json(ruta, defecto):
    if not ruta.exists():
        return defecto
    return json.loads(ruta.read_text(encoding='utf-8'))


def valor_yaml(texto):
    return json.dumps(str(texto), ensure_ascii=False)


def identificar_categoria(noticia):
    texto = (noticia.get('titulo', '') + ' ' + noticia.get('descripcion', '')).lower()
    if any(p in texto for p in ('freeride', 'line of the year', 'rampage', 'slopestyle', 'dirt jump')):
        return 'Freeride'
    if any(p in texto for p in ('cross country', 'cross-country', 'xco', 'xc race')):
        return 'XC'
    if any(p in texto for p in ('enduro', 'emtb', 'e-mtb', 'decoy', 'trail bike')):
        return 'Enduro'
    if any(p in texto for p in ('downhill', 'world cup dh', 'dh race')):
        return 'Downhill'
    return 'Downhill'


def enlaces_existentes():
    enlaces = set()
    for carpeta in (CARPETA_BORRADORES, CARPETA_PUBLICADAS):
        if not carpeta.exists():
            continue
        for archivo in carpeta.glob('*.md'):
            contenido = archivo.read_text(encoding='utf-8-sig')
            coincidencia = re.search(r'^source_url:\s*["\']?([^"\'\n]+)', contenido, re.MULTILINE)
            if coincidencia:
                enlaces.add(normalizar_url(coincidencia.group(1)))
    return enlaces


def contar_borradores_hoy():
    hoy = datetime.now(timezone.utc).date()
    cantidad = 0
    if not CARPETA_BORRADORES.exists():
        return 0
    for archivo in CARPETA_BORRADORES.glob('*.md'):
        try:
            contenido = archivo.read_text(encoding='utf-8-sig')
            coincidencia = re.search(r'^draft_created_at:\s*["\']?(\d{4}-\d{2}-\d{2})', contenido, re.MULTILINE)
            if coincidencia and date.fromisoformat(coincidencia.group(1)) == hoy:
                cantidad += 1
        except (OSError, ValueError):
            continue
    return cantidad


def contexto_de(noticia):
    contexto = noticia.get('contexto_rss') or noticia.get('descripcion') or ''
    return str(contexto).strip()[:8000]


def redactar_con_gemini(noticia):
    clave = os.getenv('GEMINI_API_KEY', '').strip()
    if not clave:
        return None, 'Sin GEMINI_API_KEY; se conserva ficha de revisión'

    contexto = contexto_de(noticia)
    titulo = str(noticia.get('titulo', '')).strip()
    if not titulo or not contexto:
        return None, 'No hay título o descripción suficiente'
