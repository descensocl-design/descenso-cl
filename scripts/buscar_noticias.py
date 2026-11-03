
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


FUENTES = {
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php",
    "Vital MTB": "https://feeds.vitalmtb.com/VitalMtbSpotlights"
}

MAX_POR_FUENTE = 50
MAX_HORAS = 72
MAX_CANDIDATAS = 5
HISTORIAL = Path("data/noticias_procesadas.json")

DISCIPLINAS = {
    "Downhill": [
        "downhill", "dh", "world cup", "gravity",
        "urban downhill", "descenso"
    ],
    "Enduro": [
        "enduro", "ews", "edr", "trail"
    ],
    "XC": [
        "cross country", "cross-country", "xco",
        "xc", "xc marathon"
    ],
    "Freeride": [
        "freeride", "red bull rampage", "slopestyle",
        "dirt jump", "big mountain"
    ]
}

LATAM = [
    "chile", "chilean", "colombia", "colombian",
    "argentina", "argentinian", "brazil",
    "brazilian", "brasil", "peru", "peruvian",
    "mexico", "mexican", "ecuador", "ecuadorian",
    "bolivia", "uruguay", "paraguay",
    "latin america", "latinoamerica",
    "valparaiso", "villarrica", "temuco",
    "martin vidaurre", "felipe agurto",
    "valentina roa", "sebastian holguin",
    "juan fernando velez", "roger vieira",
    "hans pulgar"
]


def limpiar(texto):
    texto = re.sub(r"<[^>]+>", " ", texto)
    return " ".join(html.unescape(texto).split())


def comentarios_de(texto):
    match = re.search(
        r"Comments:\s*([\d,]+)",
        texto,
        re.IGNORECASE
    )
    return int(match.group(1).replace(",", "")) if match else None


def fecha_de(texto):
    try:
        fecha = parsedate_to_datetime(texto)
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def url_limpia(url):
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
            url_limpia(url)
            for url in datos.get("procesadas", [])
            if isinstance(url, str)
        }
    except (OSError, ValueError, TypeError):
        print("Aviso: historial no disponible.")
        return set()


def clasificar(texto):
    texto = texto.lower()
    resultados = {}

    for disciplina, palabras in DISCIPLINAS.items():
        resultados[disciplina] = sum(
            1 for palabra in palabras
            if re.search(
                r"(?<!\w)" + re.escape(palabra) + r"(?!\w)",
                texto
            )
        )

    mejor = max(resultados, key=resultados.get)

    return mejor if resultados[mejor] > 0 else "General"


def relevancia_latam(texto):
    texto = texto.lower()

    coincidencias = sum(
        1 for palabra in LATAM
        if re.search(
            r"(?<!\w)" + re.escape(palabra) + r"(?!\w)",
            texto
        )
    )

    return min(100, coincidencias * 50)


def buscar_noticias():
    noticias = []
    vistas = set()
    procesadas = cargar_historial()

    ahora = datetime.now(timezone.utc)
    limite = ahora - timedelta(hours=MAX_HORAS)

    print(f"Noticias ya procesadas: {len(procesadas)}")

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
                solicitud, timeout=20
            ) as respuesta:
                contenido = respuesta.read()

            raiz = ET.fromstring(contenido)

            for item in raiz.findall(".//item")[:MAX_POR_FUENTE]:
                titulo = limpiar(item.findtext("title", ""))
                enlace = item.findtext("link", "").strip()
                fecha = fecha_de(item.findtext("pubDate", ""))
                descripcion_original = item.findtext(
                    "description", ""
                )

                if not titulo or not enlace or fecha is None:
                    continue

                if not limite <= fecha <= ahora:
                    continue

                enlace = url_limpia(enlace)

                if enlace in vistas or enlace in procesadas:
                    continue

                vistas.add(enlace)

                descripcion = limpiar(descripcion_original)
                texto = f"{titulo} {descripcion}"

                noticias.append({
                    "fuente": fuente,
                    "titulo": titulo,
                    "url": enlace,
                    "fecha": fecha.isoformat(),
                    "descripcion": descripcion[:500],
                    "comentarios": comentarios_de(
                        descripcion_original
                    ),
                    "horas": round(
                        (ahora - fecha).total_seconds() / 3600,
                        1
                    ),
                    "disciplina": clasificar(texto),
                    "latam": relevancia_latam(texto)
                })

        except Exception as error:
            print(f"No se pudo leer {fuente}: {error}")

    return noticias


def puntuar(noticias):
    max_comentarios = max(
        (n["comentarios"] or 0 for n in noticias),
        default=0
    )

    for noticia in noticias:
        comentarios = noticia["comentarios"]

        # Popularidad: 40 puntos
        if comentarios is None or max_comentarios == 0:
            popularidad = 0
        else:
            popularidad = (
                math.log1p(comentarios) /
                math.log1p(max_comentarios)
            ) * 40

        # Latinoamerica: 30 puntos
        latam = noticia["latam"] * 0.30

        # Actualidad: 20 puntos
        actualidad = max(
            0, (1 - noticia["horas"] / MAX_HORAS) * 20
        )

        # Disciplina: hasta 10 puntos
        # Es una aproximacion provisional.
        disciplina = (
            10 if noticia["disciplina"] != "General" else 0
        )

        noticia["puntos"] = round(
            popularidad + latam + actualidad + disciplina,
            1
        )

    return sorted(
        noticias,
        key=lambda n: n["puntos"],
        reverse=True
    )


def seleccionar_candidatas(ranking):
    seleccionadas = []
    usadas = set()

    # Primera pasada: favorecer disciplinas distintas
    for noticia in ranking:
        if len(seleccionadas) >= MAX_CANDIDATAS:
            break

        disciplina = noticia["disciplina"]

        if disciplina != "General" and disciplina not in usadas:
            seleccionadas.append(noticia)
            usadas.add(disciplina)

    # Segunda pasada: completar por puntuacion
    for noticia in ranking:
        if len(seleccionadas) >= MAX_CANDIDATAS:
            break

        if noticia not in seleccionadas:
            seleccionadas.append(noticia)

    return seleccionadas


if __name__ == "__main__":
    noticias = buscar_noticias()
    ranking = puntuar(noticias)
    candidatas = seleccionar_candidatas(ranking)

    print("\nDESCENSO.CL — TOP 5 CANDIDATAS\n")

    for i, noticia in enumerate(candidatas, 1):
        print(f"{i}. {noticia['titulo']}")
        print(f"   Puntuacion: {noticia['puntos']}/100")
        print(f"   Fuente: {noticia['fuente']}")
        print(f"   Disciplina: {noticia['disciplina']}")
        print(f"   Comentarios: {noticia['comentarios']}")
        print(f"   Antiguedad: {noticia['horas']} horas")
        print(f"   URL: {noticia['url']}\n")

    print(f"Noticias analizadas: {len(noticias)}")
    print(f"Candidatas seleccionadas: {len(candidatas)}")
