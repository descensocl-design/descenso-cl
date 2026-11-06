
import os
import json
import urllib.request
import urllib.error

API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def consultar_modelos():
    clave = os.environ.get("GEMINI_API_KEY")

    if not clave:
        raise SystemExit(
            "ERROR: No se encontro GEMINI_API_KEY."
        )

    modelos = []
    pagina = None

    while True:
        url = API_URL

        if pagina:
            from urllib.parse import urlencode
            url += "?" + urlencode({"pageToken": pagina})

        solicitud = urllib.request.Request(
            url,
            headers={
                "x-goog-api-key": clave,
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(
                solicitud, timeout=30
            ) as respuesta:
                datos = json.loads(
                    respuesta.read().decode("utf-8")
                )

        except urllib.error.HTTPError as error:
            detalle = error.read().decode(
                "utf-8", errors="replace"
            )
            print(f"ERROR HTTP: {error.code}")
            print(detalle[:1500])
            raise SystemExit(1)

        modelos.extend(datos.get("models", []))
        pagina = datos.get("nextPageToken")

        if not pagina:
            break

    compatibles = []

    for modelo in modelos:
        metodos = modelo.get(
            "supportedGenerationMethods", []
        )

        if "generateContent" in metodos:
            compatibles.append(modelo)

    print("====================================")
    print("MODELOS GEMINI DISPONIBLES")
    print("====================================")

    if not compatibles:
        print("No se encontraron modelos compatibles.")
        raise SystemExit(1)

    for modelo in compatibles:
        print()
        print("Modelo:", modelo.get("name"))
        print(
            "Nombre:",
            modelo.get("displayName", "")
        )
        print(
            "Metodos:",
            ", ".join(
                modelo.get(
                    "supportedGenerationMethods", []
                )
            )
        )

    print()
    print("TOTAL COMPATIBLES:", len(compatibles))
    print()
    print("PUBLICACION AUTOMATICA: DESACTIVADA")


if __name__ == "__main__":
    consultar_modelos()
