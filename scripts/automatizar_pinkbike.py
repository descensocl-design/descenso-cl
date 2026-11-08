#!/usr/bin/env python3
"""Publica hasta cinco breves diarios de Pinkbike a partir del RSS.

Por defecto simula. --publicar actualiza data/posts.json.
Requiere GEMINI_API_KEY para redactar; nunca inventa detalles faltantes.
"""
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

CANDIDATAS = Path('data/noticias_candidatas.json')
POSTS = Path('data/posts.json')
MAX_DIARIO = 5
ZONA = ZoneInfo('America/Santiago')
MODELO = os.getenv('GEMINI_MODEL', 'gemini-flash-lite-latest')


def normalizar_url(url):
    try:
        p = urlsplit(str(url).strip())
        if p.scheme != 'https' or p.hostname not in ('www.pinkbike.com', 'pinkbike.com'):
            return ''
        return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), '', ''))
    except ValueError:
        return ''


def limpiar(texto):
    texto = re.sub(r'<[^>]+>', ' ', str(texto or ''))
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def contexto_rss(noticia):
    # No se usa contenido externo ni se interpreta una URL como prueba de hechos.
    partes = [limpiar(noticia.get('titulo')), limpiar(noticia.get('descripcion'))]
    if not partes[1]:
        partes[1] = limpiar(noticia.get('contexto_rss'))
    return '\n'.join(p for p in partes if p)


def redactar_breve(noticia):
    clave = os.getenv('GEMINI_API_KEY', '').strip()
    if not clave:
        return None, 'falta GEMINI_API_KEY'
    fuente = contexto_rss(noticia)
    instrucciones = (
        'Eres redactor de Descenso.cl, un medio chileno de mountain bike. '
        'Escribe SOLO un breve periodístico en español basado estrictamente en el '
        'título y descripción RSS que siguen. Máximo 75 palabras; idealmente 35 a 65. '
        'No añadas nombres, fechas, lugares, resultados, declaraciones, cifras ni '
        'contexto que no aparezcan explícitamente en la fuente. '
        'Si el RSS es escaso, escribe menos: nunca rellenes con especulación. '
        'No agregues titular, subtítulos, enlaces, créditos, hashtags ni Markdown. '
        'No digas que se verificó el artículo completo. '
        'Si no hay información suficiente para una oración factual útil, responde '
        'exactamente SIN_DATOS.\n\nRSS:\n' + fuente
    )
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent'
    payload = {
        'contents': [{'parts': [{'text': instrucciones}]}],
        'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 350},
    }
    peticion = Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': clave},
        method='POST',
    )
    try:
        with urlopen(peticion, timeout=45) as respuesta:
            datos = json.load(respuesta)
        partes = datos.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        texto = '\n'.join(p.get('text', '') for p in partes if isinstance(p, dict)).strip()
    except Exception as exc:
        return None, f'error de Gemini: {type(exc).__name__}: {exc}'
    if not texto or 'SIN_DATOS' in texto:
        return None, 'Gemini no pudo redactar con los datos disponibles'
    texto = texto.strip().strip('"')
    if re.search(r'(?im)^\s*(#|---|title:|source_url:)', texto):
        return None, 'Gemini devolvió un formato inesperado'
    if len(texto.split()) < 12 or len(texto.split()) > 100:
        return None, f'longitud no válida: {len(texto.split())} palabras'
    return texto, None


def categoria(noticia):
    texto = contexto_rss(noticia).lower()
    if re.search(r'\b(downhill|dh|world cup|hardline)\b', texto):
        return 'Downhill'
