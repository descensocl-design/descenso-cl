import json
import os
import urllib.error
import urllib.request
from pathlib import Path

MODELO = "gemini-flash-lite-latest"
CANDIDATAS = Path("data/noticias_candidatas.json")


def main():
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise SystemExit("ERROR: falta GEMINI_API_KEY")
    if not CANDIDATAS.exists():
        raise SystemExit("ERROR: falta data/noticias_candidatas.json")

    datos = json.loads(CANDIDATAS.read_text(encoding="utf-8"))
    noticias = datos.get("noticias", [])
    if not noticias:
        raise SystemExit("ERROR: no hay noticias candidatas")

    noticia = noticias[0]
    contexto = str(noticia.get("contexto_rss") or noticia.get("descripcion") or "").strip()
    hechos = {
        "titulo_original": noticia.get("titulo", ""),
        "fuente": noticia.get("fuente", ""),
        "fecha": noticia.get("fecha", ""),
        "descripcion_rss": contexto,
        "url_fuente": noticia.get("url", ""),
    }
    print("NOTICIA SELECCIONADA:", hechos["titulo_original"], flush=True)
    print("PALABRAS DE CONTEXTO:", len(contexto.split()), flush=True)
    print("FUENTE:", hechos["url_fuente"], flush=True)

    instrucciones = (
        "Eres editor de Descenso.cl, medio chileno de mountain bike. "
        "Redacta un titular original y un texto periodistico breve en espanol de Chile "
        "a partir EXCLUSIVAMENTE de los datos JSON entregados. "
        "No inventes resultados, declaraciones, caracteristicas, ubicaciones, fechas, "
        "antecedentes, juicios de valor ni detalles del evento o producto. "
        "No afirmes haber consultado el enlace original: solo tienes los datos RSS. "
        "Si el contexto es escaso, escribe como maximo dos parrafos cortos "
        "y agrega al final: 'Informacion pendiente de verificacion editorial.' "
        "No copies extensamente la descripcion original. "
        "Devuelve solo el titular y el cuerpo, sin formato YAML.\n\n"
        "DATOS:\n" + json.dumps(hechos, ensure_ascii=False)
    )
    solicitud = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + MODELO + ":generateContent",
        data=json.dumps({
            "contents": [{"parts": [{"text": instrucciones}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 650},
        }, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": clave},
        method="POST",
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=60) as respuesta:
            resultado = json.load(respuesta)
    except urllib.error.HTTPError as error:
        print("ERROR HTTP:", error.code, flush=True)
        print(error.read().decode("utf-8", errors="replace")[:1000], flush=True)
        raise SystemExit(1)
    except urllib.error.URLError as error:
        raise SystemExit(f"ERROR DE CONEXION: {error.reason}")

    candidatos = resultado.get("candidates") or []
    partes = candidatos[0].get("content", {}).get("parts", []) if candidatos else []
    texto = "\n".join(p.get("text", "") for p in partes).strip()
    if not texto:
        raise SystemExit("ERROR: Gemini no devolvio texto")

    print("\n=== REDACCION DE PRUEBA ===\n", flush=True)
    print(texto, flush=True)
    print("\nPUBLICACION AUTOMATICA: DESACTIVADA", flush=True)
    print("NO SE MODIFICARON BORRADORES NI HISTORIAL", flush=True)


if __name__ == "__main__":
    main()
