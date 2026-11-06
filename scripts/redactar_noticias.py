
import os
import json
import urllib.request
import urllib.error

MODELO = "gemini-2.5-flash"


def probar_gemini():
    clave = os.environ.get("GEMINI_API_KEY")

    if not clave:
        raise SystemExit(
            "ERROR: No se encontró GEMINI_API_KEY en GitHub."
        )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{MODELO}:generateContent"
    )

    instrucciones = """
    Eres el redactor de Descenso.cl, un medio de mountain bike.

    Redacta un titular y un párrafo periodístico en español
    utilizando exclusivamente estos datos ficticios de prueba:

    - Una competencia de downhill se realizó en Chile.
    - Participaron 50 ciclistas.
    - La pista tenía 2 kilómetros.
    - No se conoce el nombre del ganador.

    No inventes nombres, fechas, lugares ni resultados.
    Comienza tu respuesta con el texto: PRUEBA DESCENSO.
    """

    datos = {
        "contents": [
            {
                "parts": [
                    {"text": instrucciones}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }

    solicitud = urllib.request.Request(
        url,
        data=json.dumps(datos).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": clave
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            solicitud, timeout=45
        ) as respuesta:
            resultado = json.loads(
                respuesta.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        detalle = error.read().decode(
            "utf-8", errors="replace"
        )

        print(f"ERROR HTTP: {error.code}")

        if error.code == 429:
            print("Se alcanzó un límite de uso de Gemini.")
        elif error.code == 403:
            print("Acceso denegado por Gemini.")
        elif error.code == 404:
            print("Modelo Gemini no disponible.")
        elif error.code == 400:
            print("Solicitud rechazada por Gemini.")

        print(detalle[:1500])
        raise SystemExit(1)

    except urllib.error.URLError as error:
        print(f"ERROR DE CONEXIÓN: {error.reason}")
        raise SystemExit(1)

    candidatos = resultado.get("candidates", [])

    if not candidatos:
        raise SystemExit(
            "Gemini respondió sin contenido generado."
        )

    partes = candidatos[0].get(
        "content", {}
    ).get("parts", [])

    texto = "\n".join(
        parte.get("text", "")
        for parte in partes
    )

    if not texto.strip():
        raise SystemExit("Gemini devolvió texto vacío.")

    print("CONEXIÓN CON GEMINI: CORRECTA")
    print()
    print(texto)
    print()
    print("PUBLICACIÓN AUTOMÁTICA: DESACTIVADA")


if __name__ == "__main__":
    probar_gemini()
