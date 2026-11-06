
import os
import json
import re
import hashlib
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

CANDIDATAS = Path("data/noticias_candidatas.json")
SALIDA = Path("data/pruebas-ia")
MODELO = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_PRUEBAS = 1

DOMINIOS_PERMITIDOS = (
    "pinkbike.com",
    "vitalmtb.com",
)


class ExtractorHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.textos = []
        self.ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "svg"):
            self.ignorar += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "svg"):
            self.ignorar = max(0, self.ignorar - 1)

    def handle_data(self, data):
        if not self.ignorar:
            texto = data.strip()
            if len(texto) > 35:
                self.textos.append(texto)


def consultar_url(url, datos=None, headers=None):
    solicitud = urllib.request.Request(
        url,
        data=datos,
        headers=headers or {
            "User-Agent": "Mozilla/5.0 DescensoNewsBot/1.0"
        },
        method="POST" if datos is not None else "GET"
    )

    with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
        return respuesta.read().decode("utf-8", errors="replace")


def obtener_articulo(noticia):
    url = noticia["url"]
    host = (urlparse(url).hostname or "").lower()

    if not any(
        host == dominio or host.endswith("." + dominio)
        for dominio in DOMINIOS_PERMITIDOS
    ):
        raise ValueError("Dominio de fuente no autorizado")

    html = consultar_url(url)
    extractor = ExtractorHTML()
    extractor.feed(html)

    textos = []
    vistos = set()

    for texto in extractor.textos:
        texto = re.sub(r"\s+", " ", texto).strip()
        if texto not in vistos:
            textos.append(texto)
            vistos.add(texto)

    contenido = "\n".join(textos)

    if len(contenido) < 800:
        raise ValueError("Contenido insuficiente para redactar")

    return contenido[:18000]


def redactar_con_gemini(noticia, contenido):
    clave = os.getenv("GEMINI_API_KEY")

    if not clave:
        raise ValueError("Falta el secreto GEMINI_API_KEY")

    instrucciones = f"""
Eres un periodista especializado en mountain bike de Descenso.cl.

Redacta una noticia ORIGINAL en español de Chile, con tono
periodístico profesional, claro y directo.

REGLAS OBLIGATORIAS:
- Usa exclusivamente hechos comprobables en la fuente.
- No inventes cifras, fechas, resultados ni declaraciones.
- No inventes citas textuales.
- No copies párrafos ni traduzcas literalmente la fuente.
- No agregues información externa no verificada.
- Si el contenido es insuficiente, devuelve aprobado=false.
- No incluyas imágenes.
- No uses emojis.
- No utilices titulares sensacionalistas.
- El artículo debe tener entre 150 y 350 palabras.
- Evita publicidad y contenido ajeno a la noticia.
- Devuelve exclusivamente un objeto JSON válido.

Formato:
{{
  "aprobado": true,
  "titulo": "Titular original en español",
  "descripcion": "Resumen breve de la noticia",
  "categoria": "Downhill",
  "parrafos": [
    "Primer párrafo.",
    "Segundo párrafo.",
    "Tercer párrafo."
  ]
}}

Categorías permitidas: Downhill, Enduro, Freeride, XC.
Si no puedes verificar suficientemente los hechos,
devuelve aprobado=false y parrafos=[].

DATOS DE LA NOTICIA:
Título: {noticia.get("titulo", "")}
Fecha de la fuente: {noticia.get("fecha", "")}
Fuente: {noticia.get("fuente", "")}
URL: {noticia.get("url", "")}

CONTENIDO EXTRAÍDO DE LA FUENTE:
{contenido}
"""

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + MODELO
        + ":generateContent"
    )

    cuerpo = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": instrucciones}]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    respuesta = consultar_url(
        endpoint,
        datos=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": clave
        }
    )

    datos = json.loads(respuesta)

    candidatos = datos.get("candidates", [])
    if not candidatos:
        raise ValueError("Gemini no devolvió candidatos")

    partes = candidatos[0].get("content", {}).get("parts", [])
    texto = "".join(
        parte.get("text", "")
        for parte in partes
    )

    if not texto:
        raise ValueError("Gemini devolvió una respuesta vacía")

    return json.loads(texto)


def validar_resultado(resultado):
    if resultado.get("aprobado") is not True:
        return False

    titulo = resultado.get("titulo", "")
    descripcion = resultado.get("descripcion", "")
    parrafos = resultado.get("parrafos", [])

    if not isinstance(titulo, str) or len(titulo.strip()) < 15:
        return False

    if not isinstance(descripcion, str) or len(descripcion.strip()) < 30:
        return False

    if not isinstance(parrafos, list) or len(parrafos) < 3:
        return False

    if not all(isinstance(p, str) for p in parrafos):
        return False

    palabras = sum(len(p.split()) for p in parrafos)

    if not 150 <= palabras <= 350:
        return False

    if resultado.get("categoria") not in (
        "Downhill", "Enduro", "Freeride", "XC"
    ):
        return False

    return True


def guardar_prueba(noticia, resultado):
    SALIDA.mkdir(parents=True, exist_ok=True)

    identificador = hashlib.sha256(
        noticia["url"].encode("utf-8")
    ).hexdigest()[:12]

    archivo = SALIDA / f"prueba-{identificador}.json"

    salida = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "estado": "PRUEBA_NO_PUBLICADA",
        "fuente": noticia["fuente"],
        "source_url": noticia["url"],
        "articulo": resultado
    }

    archivo.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print(f"PRUEBA CORRECTA: {archivo}", flush=True)
    print(f"Título: {resultado['titulo']}", flush=True)


def main():
    if not CANDIDATAS.exists():
        raise SystemExit("No existe noticias_candidatas.json")

    datos = json.loads(CANDIDATAS.read_text(encoding="utf-8"))
    noticias = datos.get("noticias", [])

    if not noticias:
        raise SystemExit("No hay noticias candidatas")

    exitos = 0

    for noticia in noticias:
        if exitos >= MAX_PRUEBAS:
            break

        print(
            f"Analizando: {noticia.get('titulo', '')}",
            flush=True
        )

        try:
            contenido = obtener_articulo(noticia)
            resultado = redactar_con_gemini(noticia, contenido)

            if not validar_resultado(resultado):
                print("Noticia descartada: validación fallida")
                continue

            guardar_prueba(noticia, resultado)
            exitos += 1

        except (
            ValueError,
            KeyError,
            json.JSONDecodeError,
            urllib.error.URLError,
            TimeoutError
        ) as error:
            print(f"Noticia omitida: {error}", flush=True)

    print(f"Pruebas generadas: {exitos}", flush=True)
    print("PUBLICACIÓN AUTOMÁTICA: DESACTIVADA", flush=True)

    if exitos == 0:
        raise SystemExit("No se pudo generar ninguna noticia de prueba")


if __name__ == "__main__":
    main()
