
import json
import urllib.request
import xml.etree.ElementTree as ET

FUENTES = {
    "Pinkbike": "https://www.pinkbike.com/pinkbike_xml_feed.php",
    "Vital MTB": "https://feeds.vitalmtb.com/VitalMtbSpotlights"
}


def buscar_noticias():
    noticias = []

    for nombre, url in FUENTES.items():
        print(f"Revisando {nombre}...", flush=True)

        try:
            solicitud = urllib.request.Request(
                url,
                headers={"User-Agent": "Descenso.cl News Reader/1.0"}
            )

            with urllib.request.urlopen(
                solicitud, timeout=20
            ) as respuesta:
                contenido = respuesta.read()

            raiz = ET.fromstring(contenido)

            for item in raiz.findall(".//item")[:10]:
                titulo = item.findtext("title", "").strip()
                enlace = item.findtext("link", "").strip()
                fecha = item.findtext("pubDate", "").strip()
                descripcion = item.findtext(
                    "description", ""
                ).strip()

                if titulo and enlace:
                    noticias.append({
                        "fuente": nombre,
                        "titulo": titulo,
                        "url": enlace,
                        "fecha": fecha,
                        "descripcion": descripcion[:500]
                    })

        except Exception as error:
            print(
                f"No se pudo leer {nombre}: {error}",
                flush=True
            )

    return noticias


if __name__ == "__main__":
    noticias = buscar_noticias()

    print(json.dumps(
        noticias,
        ensure_ascii=False,
        indent=2
    ))

    print(f"\nNoticias encontradas: {len(noticias)}")
