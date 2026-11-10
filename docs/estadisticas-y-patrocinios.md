# Descenso.cl — Medición y publicidad

## Cloudflare Web Analytics

El código del sitio ya incluye `/analytics.js` en la portada y noticias.
Por defecto no carga ningún servicio externo de medición.

1. En Cloudflare, activar Web Analytics para `descenso.cl` y obtener el **Site Token**.
2. Abrir `data/analytics-config.json` y completar `cloudflare_web_analytics_token` con el token exacto.
3. Publicar el cambio y comprobar en DevTools > Network que se carga `static.cloudflareinsights.com/beacon.min.js` y que Cloudflare registra visitantes.

**Importante:** no inventar tokens ni copiar IDs de otros sitios. Cloudflare Web Analytics requiere autorización en la cuenta correspondiente.

## Google Search Console

1. En Search Console, añadir una propiedad **Dominio** para `descenso.cl`.
2. Verificar propiedad mediante el registro DNS TXT solicitado en Cloudflare.
3. Enviar el sitemap `https://descenso.cl/sitemap.xml`.
4. Revisar indexación, consultas, CTR y rendimiento móvil.

La verificación DNS solo puede completarla quien administre el dominio o una integración autorizada.

## Espacios comerciales

La portada muestra un bloque **ESPACIO COMERCIAL · DISPONIBLE** y enlaza al contacto oficial.
No representa un patrocinio contratado ni muestra marcas de terceros sin acuerdo.

Ubicaciones futuras sugeridas:
- Patrocinio de portada/sidebar.
- Patrocinio de reportajes y coberturas.
- Menciones dentro de videos originales de Descenso, cuando exista acuerdo.

Toda publicidad debe estar claramente identificada y diferenciada del contenido editorial.

## Comentarios

El formulario permite nombre o anónimo y sigue publicando inmediatamente.
La API limita envíos por visitante, prohíbe enlaces y HTML, rechaza duplicados recientes y utiliza un campo antispam invisible.
El campo es una barrera básica; para entornos de mucho tráfico conviene añadir Cloudflare Turnstile, reglas WAF y seguimiento de abuso.

## Activar y comprobar los comentarios en Cloudflare

En Cloudflare Pages > proyecto de Descenso.cl > **Settings > Bindings**, enlazar una base **D1** bajo el nombre exacto `COMMENTS_DB`.
Agregar en **Variables and Secrets** la variable secreta `COMMENTS_SALT` con un valor aleatorio largo. No subirla a GitHub.
Ejecutar `database/comments.sql` en la consola de la base D1 vinculada. Sus sentencias `CREATE TABLE IF NOT EXISTS` conservan los comentarios existentes.
Desplegar nuevamente el proyecto para que el binding esté disponible en Pages Functions.

Verificación sin publicar comentarios de prueba:
- Visitar `https://descenso.cl/api/comments/2026-11-03-cual-fue-la-mejor-linea-de-freeride-de-2026-diez-finalistas-compiten-por-mas-de-10-00`.
- La respuesta debe incluir `"configured":true` y `"comments":[]` o los comentarios actuales.
- Si `configured:false`, revisar binding, `COMMENTS_SALT` y ejecución de SQL.

### Moderación y reportes

Cada comentario muestra un control **REPORTAR**, con motivos abuso, spam u otro.
Los reportes se almacenan en `comment_reports`, no publican identidades y no ocultan opiniones automáticamente.
Se limita cada visitante a una denuncia por comentario y veinte denuncias diarias.

Para priorizar la revisión, ejecutar en la consola D1:
```sql
SELECT c.id, c.article_slug, c.display_name, c.message, COUNT(r.id) AS reportes
FROM comment_reports r JOIN comments c ON c.id=r.comment_id
WHERE c.status='approved'
GROUP BY c.id ORDER BY reportes DESC, MAX(r.created_at) DESC LIMIT 50;
```
Ocultar solo si corresponde, sin destruir evidencia:
```sql
UPDATE comments SET status='rejected' WHERE id='ID_DEL_COMENTARIO';
```

**Estado:** estas operaciones requieren acceso autorizado a Cloudflare; los cambios en GitHub por sí solos no crean la base ni activan los servicios externos.
