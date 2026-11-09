# Actualización integral Descenso.cl

## Cambios
- Páginas individuales de noticias en `/noticias/fecha-titulo/`.
- Enlaces directos desde portada.
- Metadatos SEO, Open Graph, NewsArticle, sitemap y robots.
- Generación automática de páginas cuando se publican noticias mediante GitHub Actions.
- Corrección del flujo de sincronización para conservar noticias automáticas.
- Logo original conservado.

## Instalación
Subir **el contenido de esta carpeta** a la raíz del repositorio (no la carpeta contenedora). Reemplazar archivos existentes y conservar secretos de GitHub. Cloudflare Pages publica desde `main`.

## Pruebas
1. Revisar portada y hacer clic en una noticia.
2. Revisar `/sitemap.xml`.
3. Ejecutar `python scripts/generar_paginas.py` al agregar noticias manualmente fuera de los flujos automatizados.

## Limitaciones
- Los artículos breves originales siguen siendo breves; no se inventa contenido.
- Las portadas genéricas SVG no sustituyen fotografías editoriales con derechos de uso.
- El administrador existente no fue reconfigurado.
