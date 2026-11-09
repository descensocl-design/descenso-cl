# Descenso.cl — V4: recuperación del flujo editorial

- Conecta `ampliar_contexto.py` al flujo programado. Obtiene texto del artículo original cuando es públicamente accesible. Si no lo es, utiliza el RSS.
- Solo publica una noticia nueva si el material contiene al menos 95 palabras y permite escribir dos párrafos sustanciales. Si no hay suficiente contexto, la omite.
- Solicita a Gemini un artículo original de 2–6 párrafos en español, sin copiar literalmente ni inventar datos. La extensión real depende de la información disponible.
- Respeta el máximo de cinco noticias diarias y mantiene las noticias anteriores y sus URLs.
- La fotografía se obtiene exclusivamente del registro `data/imagenes_autorizadas.json`, con `approved: true`. No descarga ni republica automáticamente fotos de terceros.
- El flujo guarda `data/noticias_ampliadas.json` para diagnóstico editorial.
- Incluye `.gitignore` para evitar subir archivos temporales de Python.

## Límites importantes

El acceso al artículo original puede fallar por bloqueo o cambios de HTML. El sistema entonces omitirá más noticias, en lugar de fabricar artículos largos. No hay verificación independiente de los hechos; el texto es una síntesis atribuida a su fuente. La automatización de fotografías reales sigue condicionada a permisos.

## Publicación

Copiar el contenido del ZIP al repositorio local (sin borrar `.git`), revisar cambios, hacer commit y push. Antes de publicar se recomienda probar el workflow manualmente y revisar sus logs.
