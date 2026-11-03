
import re
import urllib.request
import xml.etree.ElementTree as ET

FUENTES = {
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php",
    "Vital MTB": "https://feeds.vitalmtb.com/VitalMtbSpotlights"
}


def extraer_comentarios(descripcion):
    coincidencia = re.search(
        r"Comments:\s*([\d,]+)",
        descripcion,
        re.IGNORECASE
    )

    if coincidencia:
        return int(coincidencia.group(1).replace(",", ""))

    return None


def buscar_noticias():
    noticias = []

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

            # Revisar hasta 50 noticias por fuente
            for item in raiz.findall(".//item")[:50]:
                titulo = item.findtext("title", "").strip()
                enlace = item.findtext("link", "").strip()
                fecha = item.findtext("pubDate", "").strip()
                descripcion = item.findtext(
                    "description", ""
                ).strip()

                if titulo and enlace:
                    comentarios = extraer_comentarios(
                        descripcion
                    )

                    noticias.append({
                        "fuente": nombre,
                        "titulo": titulo,
                        "url": enlace,
                        "fecha": fecha,
                        "descripcion": descripcion[:500],
                        "comentarios": comentarios
                    })

        except Exception as error:
            print(
                f"No se pudo leer {nombre}: {error}",
                flush=True
            )

    return noticias


if __name__ == "__main__":
    noticias = buscar_noticias()

    # Ordenar de mayor a menor cantidad de comentarios
    noticias.sort(
        key=lambda noticia: (
            noticia["comentarios"] is not None,
            noticia["comentarios"] or 0
        ),
        reverse=True
    )

    print("\nRANKING DE NOTICIAS POR COMENTARIOS\n")

    for posicion, noticia in enumerate(noticias, start=1):
        print(f"{posicion}. {noticia['titulo']}")
        print(f"   Fuente: {noticia['fuente']}")
        print(f"   Comentarios: {noticia['comentarios']}")
        print(f"   Fecha: {noticia['fecha']}")
        print(f"   URL: {noticia['url']}\n")

    print(f"Total de noticias encontradas: {len(noticias)}")
