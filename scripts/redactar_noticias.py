
import os
import json
import urllib.request
import urllib.error

# Modelo recomendado por Google en el mensaje de error
MODELO = "gemini-3.8-flash"


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
Eres el redactor de Descenso.cl, un medio especializado
en mountain bike.

Esta es una PRUEBA de conexión.

Redacta un titular y un párrafo periodístico en español
utilizando exclusivamente estos datos ficticios:

- Una competencia de downhill se realizó en Chile.
- Participaron 50 ciclistas.
- La pista tenía 2 kilómetros.
- No se conoce el nombre del ganador.

REGLAS:
- No inventes nombres de corredores.
- No inventes fechas ni lugares específicos.
- No inventes resultados.
- Utiliza un estilo periodístico profesional.
- No utilices emojis.
- Comienza con el texto: PRUEBA DESCENSO.
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
            solicitud,
            timeout=60
        ) as respuesta:
            resultado = json.loads(
                respuesta.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        detalle = error.read().decode(
            "utf-8",
            errors="replace"
        )

        print(f"ERROR HTTP: {error.code}")
        print(detalle[:2000])

        if error.code == 429:
            print("Se alcanzó el límite de uso de Gemini.")
        elif error.code == 403:
            print("Gemini rechazó el acceso.")
        elif error.code == 404:
            print("El modelo no está disponible para esta cuenta.")
        elif error.code == 400:
            print("La solicitud no fue aceptada.")

        raise SystemExit(1)

    except urllib.error.URLError as error:
        print(f"ERROR DE CONEXIÓN: {error.reason}")
        raise SystemExit(1)

    candidatos = resultado.get("candidates", [])

    if not candidatos:
        raise SystemExit(
            "Gemini respondió sin generar contenido."
        )

    partes = candidatos[0].get(
        "content", {}
    ).get("parts", [])

    texto = "\n".join(
        parte.get("text", "")
        for parte in partes
    )

    if not texto.strip():
        raise SystemExit(
            "Gemini devolvió una respuesta vacía."
        )

    print()
    print("====================================")
    print("CONEXIÓN CON GEMINI: CORRECTA")
    print("====================================")
    print()
    print(texto)
    print()
    print("PUBLICACIÓN AUTOMÁTICA: DESACTIVADA")


if __name__ == "__main__":
    probar_gemini()
