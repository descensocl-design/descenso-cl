
import json
import re
import html
import math
import urllib.request
import xml.etree.ElementTree as ET

from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, urljoin


FUENTES = {
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php",
    "Vital MTB": "https://feeds.vitalmtb.com/VitalMtbSpotlights"
}

MAX_POR_FUENTE = 50
MAX_HORAS = 72
MAX_CANDIDATAS = 5

HISTORIAL = Path("data/noticias_procesadas.json")
CANDIDATAS = Path("data/noticias_candidatas.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DescensoNewsBot/1.0)"
}


def limpiar_texto(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return " ".join(html.unescape(texto).split())


def extraer_numero(texto, patron):
    coincidencia = re.search(patron, texto or "", re.IGNORECASE)
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


class LectorMetadatos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadatos = {}
        self.jsonld = []
        self.leyendo_jsonld = False
        self.buffer = []

    def handle_starttag(self, etiqueta, atributos):
        datos = dict(atributos)

        if etiqueta == "meta":
            clave = (
                datos.get("property")
                or datos.get("name")
                or ""
            ).lower()
            valor = datos.get("content", "").strip()

            if clave and valor:
                self.metadatos.setdefault(clave, valor)

        if etiqueta == "script":
            if datos.get("type", "").lower() == "application/ld+json":
                self.leyendo_jsonld = True
                self.buffer = []

    def handle_data(self, contenido):
        if self.leyendo_jsonld:
            self.buffer.append(contenido)

    def handle_endtag(self, etiqueta):
        if etiqueta == "script" and self.leyendo_jsonld:
            self.jsonld.append("".join(self.buffer))
            self.leyendo_jsonld = False
            self.buffer = []


def recorrer_json(objeto):
    if isinstance(objeto, list):
        for elemento in objeto:
            yield from recorrer_json(elemento)

    elif isinstance(objeto, dict):
        yield objeto
        for clave in ("@graph", "mainEntity"):
            if clave in objeto:
                yield from recorrer_json(objeto[clave])


def obtener_nombre(valor):
    if isinstance(valor, str):
        return valor.strip() or None

    if isinstance(valor, dict):
        return obtener_nombre(valor.get("name"))

    if isinstance(valor, list):
        nombres = [obtener_nombre(v) for v in valor]
        return ", ".join(n for n in nombres if n) or None

    return None


def obtener_url_imagen(valor):
    if isinstance(valor, str):
        return valor

    if isinstance(valor, dict):
        return (
            valor.get("url")
            or valor.get("contentUrl")
        )

    if isinstance(valor, list):
        for elemento in valor:
            resultado = obtener_url_imagen(elemento)
            if resultado:
                return resultado

    return None


def extraer_imagen_rss(item):
    for elemento in item.iter():
        etiqueta = elemento.tag.split("}")[-1].lower()

        if etiqueta in ("thumbnail", "content", "enclosure"):
            url = elemento.attrib.get("url")
            tipo = elemento.attrib.get("type", "")

            if url and (
                etiqueta != "enclosure"
                or tipo.startswith("image/")
            ):
                return url

    descripcion = html.unescape(
        item.findtext("description", "")
    )

    coincidencia = re.search(
        r'<img[^>]+src=["\']([^"\']+)',
        descripcion,
        re.IGNORECASE
    )

    return coincidencia.group(1) if coincidencia else None


def obtener_datos_imagen(noticia):
    imagen = noticia.pop("imagen_rss", None)
    fotografo = None

    noticia["imagen"] = None
    noticia["fotografo"] = None
    noticia["credito"] = None
    noticia["fuente_imagen"] = noticia["url"]

    try:
        solicitud = urllib.request.Request(
            noticia["url"],
            headers=HEADERS
        )

        with urllib.request.urlopen(
            solicitud, timeout=15
        ) as respuesta:
            contenido = respuesta.read(1500000).decode(
                "utf-8", errors="replace"
            )

        lector = LectorMetadatos()
        lector.feed(contenido)

        meta = lector.metadatos

        imagen = (
            meta.get("og:image")
            or meta.get("twitter:image")
            or imagen
        )

        fotografo = obtener_nombre(
            meta.get("photographer")
            or meta.get("photo:creator")
        )

        for bloque in lector.jsonld:
            try:
                datos = json.loads(bloque)
            except (ValueError, TypeError):
                continue

            for entidad in recorrer_json(datos):
                tipos = entidad.get("@type", [])
                if isinstance(tipos, str):
                    tipos = [tipos]

                if "ImageObject" in tipos:
                    fotografo = fotografo or obtener_nombre(
                        entidad.get("creator")
                        or entidad.get("creditText")
                    )
                    imagen = imagen or obtener_url_imagen(
                        entidad
                    )

                if any(
                    tipo in tipos
                    for tipo in (
                        "NewsArticle",
                        "Article",
                        "BlogPosting"
                    )
                ):
                    imagen = imagen or obtener_url_imagen(
                        entidad.get("image")
                    )

    except Exception as error:
        print(
            f"No se pudieron leer metadatos de "
            f"{noticia['url']}: {error}",
            flush=True
        )

    if imagen:
        noticia["imagen"] = urljoin(
            noticia["url"], imagen
        )

    if fotografo:
        noticia["fotografo"] = fotografo
        noticia["credito"] = (
            f"Fotografía: {fotografo} / {noticia['fuente']}"
        )

    noticia["imagen_pendiente_revision"] = not bool(
        noticia["imagen"] and noticia["fotografo"]
    )

    return noticia


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
                feed, headers=HEADERS
            )

            with urllib.request.urlopen(
                solicitud, timeout=20
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
                    ),
                    "imagen_rss": extraer_imagen_rss(item)
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

    peso_comentarios = 60 if hay_votos else 85
    peso_votos = 25 if hay_votos else 0
    peso_actualidad = 15

    for noticia in noticias:
        comentarios = noticia["comentarios"] or 0
        votos = noticia["votos"] or 0

        popularidad = (
            math.log1p(comentarios)
            / math.log1p(max_comentarios)
            * peso_comentarios
            if max_comentarios > 0 else 0
        )

        puntuacion_votos = (
            math.log1p(votos)
            / math.log1p(max_votos)
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


def guardar_candidatas(candidatas):
    CANDIDATAS.parent.mkdir(
        parents=True, exist_ok=True
    )

    datos = {
        "actualizado": datetime.now(
            timezone.utc
        ).isoformat(),
        "cantidad": len(candidatas),
        "noticias": candidatas
    }

    CANDIDATAS.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(
        f"Archivo generado: {CANDIDATAS}",
        flush=True
    )


if __name__ == "__main__":
    noticias = buscar_noticias()
    ranking = calcular_ranking(noticias)

    candidatas = [
        obtener_datos_imagen(noticia)
        for noticia in ranking[:MAX_CANDIDATAS]
    ]

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
        print(f"   Imagen: {noticia['imagen']}")
        print(
            f"   Fotografo: "
            f"{noticia['fotografo'] or 'Pendiente'}"
        )
        print(f"   URL: {noticia['url']}\n")

    guardar_candidatas(candidatas)

    print(f"Noticias analizadas: {len(noticias)}")
    print(f"Candidatas seleccionadas: {len(candidatas)}")
