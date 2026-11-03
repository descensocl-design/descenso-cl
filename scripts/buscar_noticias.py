
import re
import html
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit


FUENTES = {
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php",
    "Vital MTB": "https://feeds.vitalmtb.com/VitalMtbSpotlights"
}

MAX_NOTICIAS_POR_FUENTE = 50
ANTIGUEDAD_MAXIMA_HORAS = 72


def limpiar_texto(texto):
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return " ".join(texto.split())


def extraer_comentarios(descripcion):
    coincidencia = re.search(
        r"Comments:\s*([\d,]+)",
        descripcion,
        re.IGNORECASE
    )

    if coincidencia:
        return int(
            coincidencia.group(1).replace(",", "")
        )

    return None


def convertir_fecha(fecha):
    try:
        resultado = parsedate_to_datetime(fecha)

        if resultado.tzinfo is None:
            resultado = resultado.replace(
                tzinfo=timezone.utc
            )

        return resultado.astimezone(timezone.utc)

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


def buscar_noticias():
    noticias = []
    enlaces_vistos = set()

    ahora = datetime.now(timezone.utc)
    fecha_limite = ahora - timedelta(
        hours=ANTIGUEDAD_MAXIMA_HORAS
    )

    for nombre, url in FUENTES.items():
        print(f"Revisando {nombre}...", flush=True)

        try:
            solicitud = urllib.request.Request(
                url,
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

            items = raiz.findall(".//item")

            for item in items[:MAX_NOTICIAS_POR_FUENTE]:
                titulo = item.findtext(
                    "title", ""
                ).strip()

                enlace = item.findtext(
                    "link", ""
                ).strip()

                fecha_original = item.findtext(
                    "pubDate", ""
                ).strip()

                descripcion = item.findtext(
                    "description", ""
                ).strip()

                fecha = convertir_fecha(fecha_original)

                # Excluir noticias sin fecha válida
                if fecha is None:
                    continue

                # Excluir noticias antiguas o futuras
                if fecha < fecha_limite or fecha > ahora:
                    continue

                if not titulo or not enlace:
                    continue

                enlace_normalizado = normalizar_url(
                    enlace
                )

                # Evitar duplicados en esta búsqueda
                if enlace_normalizado in enlaces_vistos:
                    continue

                enlaces_vistos.add(enlace_normalizado)

                comentarios = extraer_comentarios(
                    descripcion
                )

                noticias.append({
                    "fuente": nombre,
                    "titulo": limpiar_texto(titulo),
                    "url": enlace_normalizado,
                    "fecha": fecha.isoformat(),
                    "descripcion": limpiar_texto(
                        descripcion
                    )[:500],
                    "comentarios": comentarios,
                    "antiguedad_horas": round(
                        (ahora - fecha).total_seconds()
                        / 3600,
                        1
                    )
                })

        except Exception as error:
            print(
                f"No se pudo leer {nombre}: {error}",
                flush=True
            )

    return noticias


def ordenar_noticias(noticias):
    return sorted(
        noticias,
        key=lambda noticia: (
            noticia["comentarios"] is not None,
            noticia["comentarios"] or 0
        ),
        reverse=True
    )


if __name__ == "__main__":
    noticias = buscar_noticias()
    ranking = ordenar_noticias(noticias)

    print("\nRANKING DESCENSO.CL — ÚLTIMAS 72 HORAS\n")

    for posicion, noticia in enumerate(
        ranking,
        start=1
    ):
        print(f"{posicion}. {noticia['titulo']}")
        print(f"   Fuente: {noticia['fuente']}")
        print(f"   Comentarios: {noticia['comentarios']}")
        print(
            f"   Antigüedad: "
            f"{noticia['antiguedad_horas']} horas"
        )
        print(f"   Fecha: {noticia['fecha']}")
        print(f"   URL: {noticia['url']}\n")

    print(
        f"Total de noticias recientes: "
        f"{len(ranking)}"
    )
