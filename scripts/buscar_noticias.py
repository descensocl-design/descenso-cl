
import json
import re
import html
import math
import urllib.request
import xml.etree.ElementTree as ET

from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit


# CONFIGURACION DESCENSO.CL

FUENTES = {
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php",
    "Vital MTB": "https://feeds.vitalmtb.com/VitalMtbSpotlights"
}

MAX_POR_FUENTE = 50
MAX_HORAS = 72
MAX_CANDIDATAS = 5

HISTORIAL = Path("data/noticias_procesadas.json")


def limpiar_texto(texto):
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return " ".join(texto.split())


def extraer_numero(texto, patron):
    coincidencia = re.search(
        patron,
        texto,
        re.IGNORECASE
    )

    if not coincidencia:
        return None

    return int(
        coincidencia.group(1).replace(",", "")
    )


def extraer_interacciones(descripcion):
    comentarios = extraer_numero(
        descripcion,
        r"Comments:\s*([\d,]+)"
    )

    # Solo registrar votos si aparecen
    # explicitamente en los datos RSS.
    votos = extraer_numero(
        descripcion,
        r"(?:Likes|Votes):\s*([\d,]+)"
    )

    return comentarios, votos


def convertir_fecha(texto):
    try:
        fecha = parsedate_to_datetime(texto)

        if fecha.tzinfo is None:
            fecha = fecha.replace(
                tzinfo=timezone.utc
            )

        return fecha.astimezone(timezone.utc)

    except (TypeError, ValueError, IndexError):
        return None


def normalizar_url(url):
    partes = urlsplit(url)

    return urlunsplit((
        partes.scheme.lower(),
        partes.netloc.lower(),
        partes.path.rstrip("/"),
        "",
        ""
    ))


def cargar_historial():
    if not HISTORIAL.exists():
        return set()

    try:
        datos = json.loads(
            HISTORIAL.read_text(encoding="utf-8")
        )

        return {
            normalizar_url(url)
            for url in datos.get("procesadas", [])
            if isinstance(url, str)
        }

    except (OSError, ValueError, TypeError):
        print("Aviso: no se pudo leer el historial.")
        return set()


def buscar_noticias():
    noticias = []
    vistas = set()
    procesadas = cargar_historial()

    ahora = datetime.now(timezone.utc)
    limite = ahora - timedelta(hours=MAX_HORAS)

    print(
        f"Noticias ya procesadas: {len(procesadas)}",
        flush=True
    )

    for fuente, feed in FUENTES.items():
        print(f"Revisando {fuente}...", flush=True)

        try:
            solicitud = urllib.request.Request(
                feed,
                headers={
                    "User-Agent": "Descenso.cl News Reader/1.0"
                }
            )

            with urllib.request.urlopen(
                solicitud,
                timeout=20
            ) as respuesta:
                contenido = respuesta.read()

            raiz = ET.fromstring(contenido)

            for item in raiz.findall(".//item")[:MAX_POR_FUENTE]:
                titulo = limpiar_texto(
                    item.findtext("title", "")
                )

                enlace = item.findtext(
                    "link", ""
                ).strip()

                fecha = convertir_fecha(
                    item.findtext("pubDate", "")
                )

                descripcion_original = item.findtext(
                    "description", ""
                )

                if not titulo or not enlace or fecha is None:
                    continue

                if not limite <= fecha <= ahora:
                    continue

                enlace = normalizar_url(enlace)

                if enlace in vistas or enlace in procesadas:
                    continue

                vistas.add(enlace)

                comentarios, votos = extraer_interacciones(
                    descripcion_original
                )

                noticias.append({
                    "fuente": fuente,
                    "titulo": titulo,
                    "url": enlace,
                    "fecha": fecha.isoformat(),
                    "descripcion": limpiar_texto(
                        descripcion_original
                    )[:500],
                    "comentarios": comentarios,
                    "votos": votos,
                    "horas": round(
                        (ahora - fecha).total_seconds()
                        / 3600,
                        1
                    )
                })

        except Exception as error:
            print(
                f"No se pudo leer {fuente}: {error}",
                flush=True
            )

    return noticias


def calcular_ranking(noticias):
    if not noticias:
        return []

    max_comentarios = max(
        (n["comentarios"] or 0 for n in noticias),
        default=0
    )

    max_votos = max(
        (n["votos"] or 0 for n in noticias),
        default=0
    )

    hay_votos = max_votos > 0

    # Sin datos de votos, redistribuir su peso
    # entre comentarios y actualidad.
    peso_comentarios = 60 if hay_votos else 85
    peso_votos = 25 if hay_votos else 0
    peso_actualidad = 15

    for noticia in noticias:
        comentarios = noticia["comentarios"] or 0
        votos = noticia["votos"] or 0

        popularidad = (
            math.log1p(comentarios) /
            math.log1p(max_comentarios)
            * peso_comentarios
            if max_comentarios > 0 else 0
        )

        puntuacion_votos = (
            math.log1p(votos) /
            math.log1p(max_votos)
            * peso_votos
            if max_votos > 0 else 0
        )

        actualidad = max(
            0,
            (1 - noticia["horas"] / MAX_HORAS)
            * peso_actualidad
        )

        noticia["puntos"] = round(
            popularidad + puntuacion_votos + actualidad,
            1
        )

    return sorted(
        noticias,
        key=lambda n: (
            n["puntos"],
            n["comentarios"] or 0
        ),
        reverse=True
    )


if __name__ == "__main__":
    noticias = buscar_noticias()
    ranking = calcular_ranking(noticias)

    candidatas = ranking[:MAX_CANDIDATAS]

    print("\nDESCENSO.CL — TOP 5 POR POPULARIDAD\n")

    for posicion, noticia in enumerate(
        candidatas, start=1
    ):
        print(f"{posicion}. {noticia['titulo']}")
        print(f"   Puntuacion: {noticia['puntos']}/100")
        print(f"   Fuente: {noticia['fuente']}")
        print(f"   Comentarios: {noticia['comentarios']}")
        print(f"   Likes/votos: {noticia['votos']}")
        print(f"   Antiguedad: {noticia['horas']} horas")
        print(f"   URL: {noticia['url']}\n")

    print(f"Noticias analizadas: {len(noticias)}")
    print(f"Candidatas seleccionadas: {len(candidatas)}")
