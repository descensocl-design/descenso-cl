
#!/usr/bin/env python3
"""Amplía contexto de noticias candidatas sin publicar ni declarar hechos verificados.

Lee data/noticias_candidatas.json y genera data/noticias_ampliadas.json.
Solo visita las URL originales de dominios autorizados. Si no hay texto
editorial accesible, conserva el RSS y marca la noticia como insuficiente.
"""

import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ORIGEN = Path("data/noticias_candidatas.json")
DESTINO = Path("data/noticias_ampliadas.json")

DOMINIOS = ("pinkbike.com", "vitalmtb.com")
MAX_BYTES = 1_500_000


def dominio_permitido(url):
    try:
        partes = urlsplit(url)
        host = (partes.hostname or "").lower()

        return (
            partes.scheme == "https"
            and not partes.username
            and not partes.password
            and partes.port in (None, 443)
            and any(
                host == dominio or host.endswith("." + dominio)
                for dominio in DOMINIOS
            )
        )
    except ValueError:
        return False


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.omitir = 0
        self.partes = []
        self.capturar = 0
        self.pila = []

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        clase = (atributos.get("class") or "").lower()
        tipo = (atributos.get("itemprop") or "").lower()

        es_articulo = (
            tag == "article"
            or tipo == "articlebody"
            or bool(
                re.search(
                    r"\b(article-body|entry-content|post-content|story-body)\b",
                    clase,
                )
            )
        )

        if tag in (
            "script", "style", "nav", "footer",
            "aside", "form", "noscript"
        ):
            self.omitir += 1

        if es_articulo and not self.capturar:
            self.capturar = 1
        elif self.capturar:
            self.capturar += 1

        elementos_vacios = (
            "area", "base", "br", "col", "embed",
            "hr", "img", "input", "link", "meta",
            "param", "source", "track", "wbr"
        )

        if tag not in elementos_vacios:
            self.pila.append((tag, es_articulo))

        if self.capturar and tag in ("p", "h2", "h3", "li"):
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if self.capturar and tag in ("p", "h2", "h3", "li"):
            self.partes.append("\n")

        if self.pila and any(t == tag for t, _ in self.pila):
            while self.pila and self.pila[-1][0] != tag:
                self.pila.pop()

                if self.capturar:
                    self.capturar -= 1

            abierto, _ = self.pila.pop()

            if abierto in (
                "script", "style", "nav", "footer",
                "aside", "form", "noscript"
            ):
                self.omitir = max(0, self.omitir - 1)

            if self.capturar:
                self.capturar -= 1

    def handle_data(self, data):
        if self.capturar and not self.omitir:
            self.partes.append(data)

    def texto(self):
        lineas = [
            " ".join(linea.split())
            for linea in "".join(self.partes).splitlines()
        ]

        lineas = [
            linea for linea in lineas
            if len(linea) >= 35
        ]

        return "\n".join(lineas)[:12000]


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req, fp, code, msg, headers, newurl
    ):
        if not dominio_permitido(newurl):
            raise ValueError(
                "Redirección a dominio no permitido"
            )

        return super().redirect_request(
            req, fp, code, msg, headers, newurl
        )


def descargar(url):
    if not dominio_permitido(url):
        return "", "Dominio no permitido"

    try:
        opener = urllib.request.build_opener(
            SinRedireccion()
        )

        solicitud = urllib.request.Request(
            url,
            headers={
                "User-Agent": "DescensoNewsBot/1.0"
            }
        )

        with opener.open(
            solicitud, timeout=12
        ) as respuesta:
            tipo = respuesta.headers.get(
                "Content-Type", ""
            ).lower()

            if "text/html" not in tipo:
                return "", "Respuesta no HTML"

            datos = respuesta.read(MAX_BYTES + 1)

            if len(datos) > MAX_BYTES:
                return "", "Página demasiado grande"

            pagina = datos.decode(
                "utf-8", errors="replace"
            )

        extractor = Extractor()
        extractor.feed(pagina)

        texto = extractor.texto()

        if len(texto.split()) < 80:
            return (
                "",
                "No se encontró contenido editorial suficiente"
            )

        return texto, None

    except urllib.error.HTTPError as error:
        return (
            "",
            f"HTTP {error.code}: {error.reason}"
        )

    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        OSError,
    ) as error:
        return (
            "",
            f"No disponible: {type(error).__name__}"
        )


def main():
    if not ORIGEN.exists():
        raise SystemExit(
            f"ERROR: No existe {ORIGEN}"
        )

    datos = json.loads(
        ORIGEN.read_text(encoding="utf-8")
    )

    for noticia in datos.get("noticias", []):
        rss = str(
            noticia.get("contexto_rss")
            or noticia.get("descripcion")
            or ""
        ).strip()

        texto, error = descargar(
            str(noticia.get("url") or "")
        )

        contexto = texto or rss
        palabras = len(contexto.split())

        noticia["contexto_ampliado"] = contexto
        noticia["palabras_contexto_ampliado"] = palabras

        if palabras >= 180:
            calidad = "amplio"
        elif palabras >= 80:
            calidad = "parcial"
        else:
            calidad = "insuficiente"

        noticia["calidad_contexto_ampliado"] = calidad

        noticia["origen_contexto_ampliado"] = (
            "pagina_original" if texto else "rss"
        )

        noticia["error_ampliacion"] = error

        noticia["hechos_verificados"] = False
        noticia["aprobacion_editorial"] = False

        print(
            f"{noticia.get('fuente')}: "
            f"{palabras} palabras "
            f"({noticia['origen_contexto_ampliado']})"
            + (f" | {error}" if error else ""),
            flush=True,
        )

    DESTINO.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    DESTINO.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8",
    )

    print(
        f"Archivo generado: {DESTINO}. "
        "Publicación: DESACTIVADA"
    )


if __name__ == "__main__":
    main()
