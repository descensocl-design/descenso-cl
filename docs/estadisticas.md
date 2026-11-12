# Descenso.cl — Panel privado de estadísticas y comentarios

## Dirección y acceso

- `https://descenso.cl/admin/estadisticas.html`
- Se usa la misma clave privada `MODERATION_TOKEN` del panel de comentarios. No se almacena en localStorage ni se incluye en URL.
- API privada: `/api/stats?days=7|30|90|365`; requiere Bearer `MODERATION_TOKEN`.
- Moderación: API existente `/api/moderation` (pendientes, denunciados, publicados, ocultos).
- No se modificó la integración de Meta ni se creó ninguna conexión adicional con Instagram.

## Datos medidos

- **Sesiones estimadas:** cuenta identificadores aleatorios de pestaña, con hash distinto por día; no son visitantes únicos ni datos demográficos.
- **Vistas de página:** páginas vistas de portada `/` y noticias `/noticias/.../`.
- **Clics en noticias:** clics desde la portada hacia artículos.
- **Clics externos:** YouTube, Instagram, TikTok, WhatsApp y otros.
- **Reproductores de YouTube cargados:** evento iframe load; no representa inicio de video ni vistas reales.
- **Comentarios:** total, pendientes, visibles, ocultos, denuncias y actividad por noticia.

El script `analytics.js` recopila eventos sin cookies, sin IP en D1 y sin parámetros de URL. Respeta Do Not Track (DNT) y Global Privacy Control (GPC). El conteo comienza al activarse; no reconstruye visitas anteriores. Los datos pueden excluir visitas por bloqueadores de scripts, restricciones del navegador o preferencia DNT.

Las reproducciones reales de YouTube se consultan en YouTube Studio. Clics y consultas de búsqueda en Google se consultan en Search Console. El panel no pretende sumar datos de esas dos plataformas sin su autorización y una integración específica.

## Comentarios y moderación

- **Nuevos comentarios:** se registran con estado `pending`, no visibles hasta aprobación. Los comentarios anteriores mantienen su estado previo.
- **Aprobar:** pasa de `pending` a `approved` (visible).
- **Rechazar/ocultar:** pasa a `rejected` (no visible).
- **Restaurar:** pasa de `rejected` a `approved`.
- **Eliminar definitivamente:** elimina comentario y denuncias asociadas; no se puede deshacer; exige confirmación en interfaz.

## Datos y despliegue

- Tablas D1: `web_stats_daily` (agregados diarios), `web_stats_sessions` (hash anónimo por día).
- Las tablas de comentarios `comments` y `comment_reports` preexistentes siguen intactas salvo las acciones explícitas de moderación.
- Solo el panel autenticado consulta datos agregados desde `/api/stats`.
- Cloudflare Web Analytics sigue siendo un servicio independiente: si está desactivado no afecta al contador propio.
