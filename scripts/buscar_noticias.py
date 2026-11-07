
import json
import re
import html
import math
import struct
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
            if (
                datos.get("type", "").lower()
                == "application/ld+json"
            ):
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
        nombres = [
            obtener_nombre(elemento)
            for elemento in valor
        ]
        return ", ".join(
            nombre for nombre in nombres if nombre
        ) or None

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

        if etiqueta in (
            "thumbnail",
            "content",
            "enclosure"
        ):
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

    if coincidencia:
        return coincidencia.group(1)

    return None


def leer_dimensiones_imagen(datos):
    """
    Lee las dimensiones de JPEG o PNG sin
    descargar la fotografia completa.
    """
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(datos) >= 24:
            return struct.unpack(">II", datos[16:24])

    if not datos.startswith(b"\xff\xd8"):
        return None

    posicion = 2

    marcadores_sof = {
        0xC0, 0xC1, 0xC2, 0xC3,
        0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB,
        0xCD, 0xCE, 0xCF
    }

    while posicion + 4 <= len(datos):
        if datos[posicion] != 0xFF:
            posicion += 1
            continue

        while (
            posicion < len(datos)
            and datos[posicion] == 0xFF
        ):
            posicion += 1

        if posicion >= len(datos):
            break

        marcador = datos[posicion]
        posicion += 1

        if marcador in (0xD8, 0xD9):
            continue

        if marcador == 0xDA:
            break

        if posicion + 2 > len(datos):
            break

        longitud = struct.unpack(
            ">H", datos[posicion:posicion + 2]
        )[0]

        if longitud < 2:
            break

        if marcador in marcadores_sof:
            if posicion + 7 <= len(datos):
                alto, ancho = struct.unpack(
                    ">HH",
                    datos[posicion + 3:posicion + 7]
                )
                return ancho, alto

        posicion += longitud

    return None


def comprobar_imagen(url):
    """
    Comprueba que la imagen exista y tenga
    al menos 1000 pixeles de ancho.
    """
    try:
        solicitud = urllib.request.Request(
            url,
            headers={
                **HEADERS,
                "Range": "bytes=0-65535"
            }
        )

        with urllib.request.urlopen(
            solicitud, timeout=12
        ) as respuesta:
            tipo = respuesta.headers.get(
                "Content-Type", ""
            ).lower()

            if not tipo.startswith("image/"):
                return False

            datos = respuesta.read(65536)

        dimensiones = leer_dimensiones_imagen(datos)

        if not dimensiones:
            print(
                f"No se pudo verificar resolucion: {url}",
                flush=True
            )
            return False

        ancho, alto = dimensiones

        print(
            f"Imagen comprobada: {ancho}x{alto} - {url}",
            flush=True
        )

        return ancho >= ANCHO_MINIMO

    except Exception as error:
        print(
            f"No se pudo comprobar imagen {url}: {error}",
            flush=True
        )
        return False


def obtener_imagen_alta_resolucion(url, fuente):
    """
    En Pinkbike intenta cambiar p2pb por p5pb.

    Solo utiliza la version ampliada cuando
    comprueba que tiene resolucion suficiente.

    Devuelve:
        (url, alta_resolucion_verificada)
    """
    if not url:
        return None, False

    if fuente != "Pinkbike":
        return url, False

    partes = urlsplit(url)

    if not partes.netloc.lower().endswith(
        ".pinkbike.org"
    ):
        return url, False

    ruta = partes.path

    coincidencia = re.search(
        r"/p\d+pb(\d+)/p\d+pb\1\.(jpg|jpeg|png)$",
        ruta,
        re.IGNORECASE
    )

    if not coincidencia:
        return url, False

    identificador = coincidencia.group(1)
    extension = coincidencia.group(2)

    ruta_grande = (
        f"/p5pb{identificador}/"
        f"p5pb{identificador}.{extension}"
    )

    url_grande = urlunsplit((
        partes.scheme,
        partes.netloc,
        ruta_grande,
        "",
        ""
    ))

    if comprobar_imagen(url_grande):
        print(
            f"Imagen de alta resolucion seleccionada: "
            f"{url_grande}",
            flush=True
        )
        return url_grande, True

    print(
        f"No se confirmo version grande para {url}",
        flush=True
    )

    return url, False


def obtener_datos_imagen(noticia):
    imagen = noticia.pop("imagen_rss", None)
    fotografo = None

    noticia["imagen"] = None
    noticia["fotografo"] = None
    noticia["credito"] = None
    noticia["fuente_imagen"] = noticia["url"]
    noticia["imagen_pendiente_revision"] = True
    noticia["imagen_alta_resolucion"] = False

    try:
        solicitud = urllib.request.Request(
            noticia["url"],
            headers=HEADERS
        )

        with urllib.request.urlopen(
            solicitud, timeout=12
        ) as respuesta:
            contenido = respuesta.read(
                1500000
            ).decode(
                "utf-8",
                errors="replace"
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
                    imagen = imagen or obtener_url_imagen(
                        entidad
                    )

                    fotografo = fotografo or obtener_nombre(
                        entidad.get("creator")
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
            f"Metadatos no disponibles para "
            f"{noticia['url']}: {error}",
            flush=True
        )

    if imagen:
        imagen = urljoin(noticia["url"], imagen)

        if urlsplit(imagen).scheme in ("http", "https"):
            imagen, alta_resolucion = (
                obtener_imagen_alta_resolucion(
                    imagen,
                    noticia["fuente"]
                )
            )

            noticia["imagen"] = imagen
            noticia["imagen_alta_resolucion"] = (
                alta_resolucion
            )

    if fotografo:
        noticia["fotografo"] = fotografo
        noticia["credito"] = (
            f"Fotografía: {fotografo} / "
            f"{noticia['fuente']}"
        )

    elif noticia["imagen"]:
        if noticia["fuente"] == "Pinkbike":
            noticia["credito"] = (
                "Fotografía obtenida del sitio oficial "
                "de Pinkbike (www.pinkbike.com)"
            )
        else:
            noticia["credito"] = (
                f"Imagen obtenida de {noticia['fuente']}"
            )

    noticia["imagen_pendiente_revision"] = bool(
        noticia["imagen"]
        and (
            not noticia["fotografo"]
            or not noticia["imagen_alta_resolucion"]
        )
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
                feed,
                headers=HEADERS
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

                contenido_rss = extraer_contenido_rss(item)

                noticias.append({
                    "fuente": fuente,
                    "titulo": titulo,
                    "url": enlace,
                    "fecha": fecha.isoformat(),
                    "descripcion": limpiar_texto(
                        descripcion_original
                    )[:500],
                    "contexto_rss": contenido_rss,
                    "palabras_contexto": len(contenido_rss.split()),
                    "calidad_contexto": evaluar_contexto(contenido_rss),
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
        parents=True,
        exist_ok=True
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
        candidatas,
        start=1
    ):
        print(f"{posicion}. {noticia['titulo']}")
        print(
            f"   Puntuacion: "
            f"{noticia['puntos']}/100"
        )
        print(
            f"   Fuente: {noticia['fuente']}"
        )
        print(
            f"   Contexto RSS: {noticia['palabras_contexto']} palabras "
            f"({noticia['calidad_contexto']})"
        )
        print(
            f"   Comentarios: "
            f"{noticia['comentarios']}"
        )
        print(
            f"   Likes/votos: "
            f"{noticia['votos']}"
        )
        print(
            f"   Antiguedad: "
            f"{noticia['horas']} horas"
        )
        print(
            f"   Imagen: {noticia['imagen']}"
        )
        print(
            f"   Alta resolucion: "
            f"{noticia['imagen_alta_resolucion']}"
        )
        print(
            f"   Fotografo: "
            f"{noticia['fotografo'] or 'No identificado'}"
        )
        print(
            f"   Credito: "
            f"{noticia['credito'] or 'Sin imagen'}"
        )
        print(
            f"   Revision: "
            f"{noticia['imagen_pendiente_revision']}"
        )
        print(
            f"   URL: {noticia['url']}\n"
        )

    guardar_candidatas(candidatas)

    print(
        f"Noticias analizadas: {len(noticias)}"
    )
    print(
        f"Candidatas seleccionadas: {len(candidatas)}"
    )