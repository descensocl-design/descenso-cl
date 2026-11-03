# DESCENSO.CL — Primera versión

Sitio editorial estático para Cloudflare Pages, sin frameworks ni dependencias de compilación.

## Publicación

Sube **index.html**, **styles.css**, **script.js** y la carpeta **data** a la raíz del repositorio `descenso-cl` en GitHub. Cloudflare Pages desplegará los cambios automáticamente.

## Configuración Cloudflare Pages

- Framework: None
- Build command: vacío
- Output directory: `/`

## Agregar una noticia (provisional)

Edita `data/posts.json` desde GitHub. Agrega un objeto JSON con: `title`, `date` (AAAA-MM-DD), `category` (Downhill, Enduro, XC, Freeride o Videos), `excerpt`, `image` (URL HTTPS de una imagen con permiso de uso, o vacío), `youtube` (URL de YouTube, o vacío), `body` (lista de párrafos) y `link` (URL externa HTTPS opcional). Mantén comas y comillas correctamente.

Este es un sistema provisional: **todavía no hay panel de administración**. Se añadirá en una siguiente etapa con autenticación segura.

## Notas

- Las 3 noticias incluidas son demostraciones, no noticias periodísticas.
- No hace falta modificar DNS ni el subdominio `contacto.descenso.cl` para probar la web.
- Los videos se incrustan desde YouTube, no se almacenan en Cloudflare.
