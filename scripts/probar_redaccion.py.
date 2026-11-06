
import os
import json
import urllib.request
import urllib.error

MODELO = "gemini-flash-lite-latest"


def main():
    clave = os.environ.get("GEMINI_API_KEY")

    if not clave:
        raise SystemExit("Falta GEMINI_API_KEY")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{MODELO}:generateContent"
    )

    datos = {
        "contents": [{
            "parts": [{
                "text": (
                    "Escribe un titular y un párrafo periodístico "
                    "en español para Descenso.cl utilizando "
                    "exclusivamente estos datos ficticios: "
                    "una carrera de downhill en Chile, "
                    "50 participantes y una pista de 2 km. "
                    "No inventes resultados, nombres ni fechas. "
                    "Comienza con PRUEBA DESCENSO."
                )
            }]
        }],
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
            solicitud, timeout=60
        ) as respuesta:
            resultado = json.load(respuesta)

    except urllib.error.HTTPError as error:
        detalle = error.read().decode(
            "utf-8", errors="replace"
        )
        print(f"ERROR HTTP {error.code}")
        print(detalle[:1500])
        raise SystemExit(1)

    partes = (
        resultado.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )

    texto = "\n".join(
        parte.get("text", "")
        for parte in partes
    )

    if not texto.strip():
        raise SystemExit("Gemini no devolvió texto.")

    print("CONEXIÓN Y REDACCIÓN CORRECTAS")
    print("MODELO:", MODELO)
    print()
    print(texto)
    print()
    print("PUBLICACIÓN AUTOMÁTICA: DESACTIVADA")


if __name__ == "__main__":
    main()
