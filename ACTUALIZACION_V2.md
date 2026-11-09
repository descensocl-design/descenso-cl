# Descenso.cl — actualización editorial v2

## Incluye
- Titulares en español para cinco publicaciones antiguas, sin cambiar sus URLs ya compartidas.
- Imágenes de respaldo por categoría en la portada y páginas individuales.
- Etiqueta visible para distinguir imágenes de referencia de fotografías de noticias.
- Tipografía y espaciado más legibles en artículos.
- Archivo `data/imagenes_autorizadas.json` para vincular imágenes reales **solo cuando se haya verificado su permiso de uso**. No se descargan ni copian automáticamente fotos de Pinkbike.
- Publicaciones nuevas siguen usando Gemini y las mismas restricciones de no inventar información.

## Cómo autorizar una imagen
Agregar al JSON una entrada como `"https://www.pinkbike.com/news/ejemplo.html": {"image": "https://dominio-autorizado.com/foto.jpg", "approved": true}`. Verificar derechos y estabilidad de la URL antes de hacerlo. Para imágenes propias, conviene subirlas a `/assets/fotos/` y extender el sistema para rutas locales.

## Publicación
Copiar el contenido de esta carpeta sobre el repositorio local, sin borrar `.git`, revisar cambios en GitHub Desktop, Commit y Push. El workflow genera las páginas para nuevas publicaciones. No se modificaron credenciales ni secretos.

## Pendiente
Conseguir licencias/permiso para fotografías reales. El RSS y los metadatos de origen no otorgan por sí mismos permiso de republicación.
