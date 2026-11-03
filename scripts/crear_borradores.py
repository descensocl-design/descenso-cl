
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone, date
from urllib.parse import urlsplit, urlunsplit


CANDIDATAS = Path("data/noticias_candidatas.json")
HISTORIAL = Path("data/noticias_procesadas.json")
CARPETA_BORRADORES = Path("data/borradores-ia")
CARPETA_PUBLICADAS = Path("data/noticias")

MAX_BORRADORES_DIA = 5


def normalizar_url(url):
    partes = urlsplit(url.strip())
    return urlunsplit((
        partes.scheme.lower(),
        partes.netloc.lower(),
        partes.path.rstrip("/"),
        "",
        ""
    ))


def cargar_json(ruta, defecto):
    if not ruta.exists():
        return defecto

    return json.loads(ruta.read_text(encoding="utf-8"))


def valor_yaml(texto):
    return json.dumps(str(texto), ensure_ascii=False)


def identificar_categoria(noticia):
    texto = (
        noticia.get("titulo", "") + " " +
        noticia.get("descripcion", "")
    ).lower()

    if any(p in texto for p in [
        "freeride", "line of the year", "rampage",
        "slopestyle", "dirt jump"
    ]):
        return "Freeride"

    if any(p in texto for p in [
        "cross country", "cross-country", "xco", "xc race"
    ]):
        return "XC"

    if any(p in texto for p in [
        "enduro", "emtb", "e-mtb", "decoy", "trail bike"
    ]):
        return "Enduro"

    if any(p in texto for p in [
        "downhill", "world cup dh", "dh race"
    ]):
        return "Downhill"

    return "Downhill"


def enlaces_existentes():
    enlaces = set()

    for carpeta in [CARPETA_BORRADORES, CARPETA_PUBLICADAS]:
        if not carpeta.exists():
            continue

        for archivo in carpeta.glob("*.md"):
            contenido = archivo.read_text(
                encoding="utf-8-sig"
            )

            coincidencia = re.search(
                r'^source_url:\s*["\']?([^"\'\n]+)',
                contenido,
                re.MULTILINE
            )

            if coincidencia:
                enlaces.add(
                    normalizar_url(coincidencia.group(1))
                )

    return enlaces


def contar_borradores_hoy():
    hoy = datetime.now(timezone.utc).date()
    cantidad = 0

    if not CARPETA_BORRADORES.exists():
        return 0

    for archivo in CARPETA_BORRADORES.glob("*.md"):
        try:
            contenido = archivo.read_text(
                encoding="utf-8-sig"
            )

            coincidencia = re.search(
                r'^draft_created_at:\s*["\']?(\d{4}-\d{2}-\d{2})',
                contenido,
                re.MULTILINE
            )

            if coincidencia:
                fecha = date.fromisoformat(
                    coincidencia.group(1)
                )

                if fecha == hoy:
                    cantidad += 1

        except (OSError, ValueError):
            continue

    return cantidad


def crear_borrador(noticia):
    url = normalizar_url(noticia["url"])

    identificador = hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:12]

    fecha_creacion = datetime.now(timezone.utc)
    fecha_noticia = noticia.get(
        "fecha", fecha_creacion.isoformat()
    )

    titulo = noticia.get("titulo", "Noticia MTB")
    categoria = identificar_categoria(noticia)

    imagen = noticia.get("imagen") or ""
    fotografo = noticia.get("fotografo") or ""

    credito = noticia.get("credito") or ""

    if imagen and not credito:
        credito = (
            "Fotografía obtenida del sitio oficial "
            "de Pinkbike (www.pinkbike.com)"
            if noticia.get("fuente") == "Pinkbike"
            else f"Imagen obtenida de {noticia.get('fuente', 'fuente original')}"
        )

    pendiente = bool(
        noticia.get("imagen_pendiente_revision", False)
    )

    nombre_archivo = (
        fecha_creacion.strftime("%Y-%m-%d")
        + "-"
        + identificador
        + ".md"
    )

    ruta = CARPETA_BORRADORES / nombre_archivo

    descripcion = noticia.get("descripcion", "")

    contenido = "\n".join([
        "---",
        f"title: {valor_yaml(titulo)}",
        f"date: {valor_yaml(fecha_noticia)}",
        f"category: {valor_yaml(categoria)}",
        f"source_url: {valor_yaml(url)}",
        f"image: {valor_yaml(imagen)}",
        f"image_credit: {valor_yaml(credito)}",
        f"photographer: {valor_yaml(fotografo)}",
        f"image_pending_review: {str(pendiente).lower()}",
        f"draft_created_at: {valor_yaml(fecha_creacion.isoformat())}",
        "---",
        "",
        "**BORRADOR AUTOMÁTICO — PENDIENTE DE REDACCIÓN Y APROBACIÓN**",
        "",
        "Esta ficha se creó automáticamente a partir de una noticia",
        "seleccionada por el buscador de Descenso.cl.",
        "",
        f"**Título original:** {titulo}",
        "",
        f"**Fuente:** {noticia.get('fuente', 'Pinkbike')}",
        "",
        f"**Descripción de referencia:** {descripcion}",
        "",
        f"**Artículo original:** {url}",
        "",
        "Antes de publicar, redactar una noticia original en español,",
        "verificar los datos y revisar los créditos de las imágenes.",
        ""
    ])

    ruta.write_text(contenido, encoding="utf-8")

    print(f"Borrador creado: {ruta}", flush=True)

    return ruta


def main():
    if not CANDIDATAS.exists():
        print("ERROR: No existe noticias_candidatas.json")
        raise SystemExit(1)

    datos = cargar_json(CANDIDATAS, {})
    noticias = datos.get("noticias", [])

    historial = cargar_json(
        HISTORIAL, {"procesadas": []}
    )

    procesadas = {
        normalizar_url(url)
        for url in historial.get("procesadas", [])
        if isinstance(url, str)
    }

    existentes = enlaces_existentes()

    creados_hoy = contar_borradores_hoy()
    disponibles = max(
        0, MAX_BORRADORES_DIA - creados_hoy
    )

    print(f"Borradores creados hoy: {creados_hoy}")
    print(f"Cupos disponibles: {disponibles}")

    CARPETA_BORRADORES.mkdir(
        parents=True, exist_ok=True
    )

    nuevos = 0

    for noticia in noticias:
        if nuevos >= disponibles:
            break

        url = normalizar_url(
            noticia.get("url", "")
        )

        if not url:
            continue

        if url in procesadas or url in existentes:
            print(f"Noticia duplicada: {url}")
            continue

        crear_borrador(noticia)

        procesadas.add(url)
        existentes.add(url)
        nuevos += 1

    historial["procesadas"] = sorted(procesadas)

    HISTORIAL.parent.mkdir(
        parents=True, exist_ok=True
    )

    HISTORIAL.write_text(
        json.dumps(
            historial,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(f"Nuevos borradores creados: {nuevos}")
    print("Publicación automática: DESACTIVADA")


if __name__ == "__main__":
    main()
