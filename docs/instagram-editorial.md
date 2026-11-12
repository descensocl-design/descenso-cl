# Integración de Descenso.cl con Instagram @descenso.cl

## Estado
- Panel privado: `https://descenso.cl/admin/instagram.html`.
- Las noticias de `data/posts.json` generan automáticamente una portada JPG original 1080 x 1350 en `assets/instagram/<slug>.jpg` mediante `scripts/generar_instagram.py`.
- GitHub Actions corre este generador junto con la publicación de noticias y sincroniza las portadas.
- Los borradores se guardan en Cloudflare D1 (`COMMENTS_DB`, tabla `social_ig_posts`, creada en el primer acceso autenticado).
- La autorización de administrador utiliza el secreto existente `MODERATION_TOKEN`.
- La publicación real permanece **desactivada** mientras no se configure Meta.

## Activar publicación mediante Meta API
1. Confirmar que @descenso.cl es una cuenta profesional (Empresa o Creador).
2. Utilizar la aplicación ya creada **Descenso CL Noticias** y su caso de uso **API de Instagram (inicio de sesión unificado)**. Este flujo utiliza un token de usuario del sistema (SUAT) y Facebook Graph API (`graph.facebook.com`).
3. Autorizar la cuenta profesional y obtener un token de acceso válido con los permisos `instagram_basic` y `instagram_content_publish`. Obtener también el ID numérico de la cuenta profesional Instagram correspondiente. Los permisos y el flujo están sujetos a los requisitos actuales de Meta.
4. En Cloudflare > Workers y Pages > `descenso-cl` > Configuración > **Producción** > Variables y secretos, crear:
   - `INSTAGRAM_ACCESS_TOKEN` — tipo **Secreto**, token profesional de Meta.
   - `INSTAGRAM_USER_ID` — ID numérico de la cuenta profesional, variable de entorno (o secreto).
5. Guardar y desplegar nuevamente Pages para que las funciones reciban las variables.
6. Abrir `/admin/instagram.html`, entrar con `MODERATION_TOKEN` y confirmar el indicador **META CONECTADO**.
7. Seleccionar una noticia, revisar y corregir el texto y la portada generada. Confirmar derechos y guardar el borrador. En primera prueba, publicar solo una noticia autorizada.
8. Hacer clic en **PUBLICAR EN INSTAGRAM** y confirmar. El panel crea el contenedor de imagen en Meta, espera que esté listo y envía la publicación.

## Seguridad y criterios editoriales
- Las portadas son composiciones tipográficas propias, sin reutilizar fotografías de terceros.
- La foto que se publica debe ser públicamente accesible por HTTPS, formato JPEG.
- Cada publicación exige confirmación de derechos de imagen y una acción explícita de aprobación.
- Se conserva un registro de publicación en D1 para evitar publicaciones duplicadas por noticia.
- Nunca pegar tokens de Meta ni de Cloudflare en ChatGPT, GitHub, scripts o capturas públicas.
- Los enlaces en captions de Instagram generalmente no son clicables; CTA recomendado: «Lee la noticia completa en Descenso.cl. Enlace en la biografía».
- Los tokens de Meta pueden expirar o revocarse: prever renovación y comprobación de permisos.
- Los posts ya marcados como publicados en D1 no vuelven a enviarse desde el panel.
- Si la conexión con Meta está pendiente, el panel sigue permitiendo editar, copiar y guardar borradores.

## Diagnóstico
- `GET /api/instagram` sin Bearer debe devolver HTTP 401.
- El estado de Meta y las noticias están disponibles solo tras autenticar el panel.
- Si falla la publicación, revisar la respuesta de Meta en el panel, los permisos del token y que la imagen sea JPEG pública.
- Las noticias se detectan automáticamente de `/data/posts.json` y no requieren crear manualmente filas nuevas en D1.
