#!/usr/bin/env python3
"""Clasifica candidatas de Descenso.cl sin modificar el buscador ni publicar.

Entrada: data/noticias_candidatas.json
Salida:  data/contenidos_clasificados.json

Clasificacion heuristica: no verifica hechos ni aprueba publicaciones.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ENTRADA = Path('data/noticias_candidatas.json')
SALIDA = Path('data/contenidos_clasificados.json')

# Los patrones mas especificos se evaluan antes de los genericos.
VIDEOS = [
    r'\bvideo\s*:', r'\bwatch\s*:', r'\bfilm\s*:',
    r'\b(documentary|documental|trailer|teaser|short film|full film)\b',
    r'\b(behind the scenes|webisode|episode|episodio)\b',
]
OPINION = [
    r'\b(opinion|editorial|column|opini[oó]n|columna)\s*:',
    r'\b(review|reseña|comparativa|comparison|shootout|roundup)\b',
    r'\b(favorite|favourite|favorites|favourites|best of|top \d+)\b',
    r'\b(poll|survey|vote|voting|encuesta|votaci[oó]n)\b',
    r'\b(first ride|first look|tested|on test|long-term test)\s*:',
]
NOTICIAS = [
    r'\b(acquisition|acquires|acquired|buyout|merger|insolvency|closure|shutdown)\b',
    r'\b(reorganization|reorganisation|restructuring|bankruptcy)\b',
    r'\b(signs|signed|signing|joins|leaves|transfer|fichaje|contrata)\b',
    r'\b(wins|won|victory|podium|champion|championship|results|resultados)\b',
    r'\b(announces|announced|launches|launched|unveils|reveals)\b',
    r'\b(cancels|cancelled|postponed|suspended|injured|injury)\b',
    r'\b(world cup|world championships|uci|copa del mundo|mundial)\b',
]


def coincide(patrones, texto):
    return any(re.search(p, texto, flags=re.IGNORECASE) for p in patrones)


def clasificar(noticia):
    titulo = str(noticia.get('titulo') or '').strip()
    descripcion = str(noticia.get('descripcion') or '').strip()
    texto = f'{titulo} {descripcion}'
    if not titulo:
        return 'pendientes', 'Sin titulo'

    # Las etiquetas editoriales explicitas tienen prioridad sobre palabras
    # de carreras o lanzamientos mencionadas en un video o una opinion.
    if coincide(VIDEOS, titulo):
        return 'videos', 'Titulo identificado como contenido audiovisual'
    if coincide(OPINION, titulo):
        return 'opinion_analisis', 'Titulo identificado como opinion o analisis'
    if coincide(NOTICIAS, texto):
        return 'noticias', 'Indicios de acontecimiento noticioso'
    return 'pendientes', 'Tipo de contenido ambiguo; requiere revision'


def main():
    if not ENTRADA.is_file():
        raise SystemExit(f'ERROR: no existe {ENTRADA}')
    datos = json.loads(ENTRADA.read_text(encoding='utf-8'))
    candidatas = datos.get('noticias')
    if not isinstance(candidatas, list):
        raise SystemExit('ERROR: noticias debe ser una lista')

    grupos = {'noticias': [], 'videos': [], 'opinion_analisis': [], 'pendientes': []}
    for candidata in candidatas:
        if not isinstance(candidata, dict):
            continue
        categoria, motivo = clasificar(candidata)
        registro = dict(candidata)
        registro['tipo_contenido'] = categoria
        registro['motivo_clasificacion'] = motivo
        registro['verificado'] = False
        registro['aprobacion_editorial'] = False
        grupos[categoria].append(registro)
        print(f'[{categoria}] {registro.get("titulo", "")} | {motivo}')

    salida = {
        'actualizado': datetime.now(timezone.utc).isoformat(),
        'origen': str(ENTRADA),
        'advertencia': 'Clasificacion automatica orientativa; no verifica ni publica.',
        'totales': {nombre: len(elementos) for nombre, elementos in grupos.items()},
        **grupos,
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Resultado: {SALIDA} | Publicacion: DESACTIVADA')


if __name__ == '__main__':
    main()
