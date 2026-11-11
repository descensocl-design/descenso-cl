# Descenso.cl — Medición y publicidad

## Cloudflare Web Analytics

**Ruta recomendada (sin tokens ni código manual):**
1. Entrar en Cloudflare > **Workers & Pages** > proyecto Pages de Descenso.cl.
2. Abrir **Metrics** y pulsar **Enable** en **Web Analytics**.
3. Esperar al siguiente despliegue: Cloudflare inyecta automáticamente el beacon de medición.
4. Consultar **Web Analytics** en la cuenta de Cloudflare para comprobar tráfico.

El sitio también conserva un mecanismo alternativo `/analytics.js` con `data/analytics-config.json`, desactivado por defecto. **No poner un token manual** si ya se habilita la inyección automática desde el panel, para no duplicar mediciones.

Referencia oficial: https://developers.cloudflare.com/pages/how-to/web-analytics/

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

## Panel privado de moderación

Panel preparado en `https://descenso.cl/admin/comentarios.html`.
La ruta no se enlaza desde la portada y tiene metadatos de no indexación. La **seguridad real** está en la API, no en ocultar la dirección.

En **Cloudflare Pages > Settings > Variables and Secrets** registrar `MODERATION_TOKEN` como secreto de **al menos 32 caracteres aleatorios**. Usar un valor diferente de `COMMENTS_SALT`. No subir el token a GitHub, ni enviarlo por correo o por este chat.

Después de desplegar Pages, ingresar al panel con ese token. El panel permite ver comentarios denunciados, recientes u ocultos, y cambiar un comentario de `approved` a `rejected` o al revés. El token solo reside en la memoria de la pestaña mientras se utiliza; recargar o cerrar la página requiere ingresarlo de nuevo.

Comprobación sin publicar datos privados:
- Abrir `https://descenso.cl/api/moderation` sin token. Debe devolver **401** si D1 está vinculada y el endpoint está desplegado.
- Confirmar que `https://descenso.cl/admin/comentarios.html` muestra la pantalla de ingreso.
- Con el token real, confirmar que el listado de denuncias carga sin errores. Si responde 503, revisar la base D1 y el esquema `database/comments.sql`.
- Una vez que existan denuncias reales, usar el panel para revisar el contenido antes de ocultarlo.

Por seguridad no se habilita un panel de acceso público ni se genera un token predeterminado. La API comprueba el token de forma segura y no lo devuelve en sus respuestas. Configurar Cloudflare WAF para limitar intentos reiterados sobre `/api/moderation` es recomendable.

## Estado de activación (10 de noviembre de 2026)

- Código y esquema de comentarios, denuncias y moderación: preparados en GitHub.
- Binding `COMMENTS_DB`, secretos `COMMENTS_SALT` y `MODERATION_TOKEN`: requieren configuración en la cuenta de Cloudflare.
- Cloudflare Web Analytics: requiere token específico de la propiedad.
- Search Console: requiere verificación DNS.
- El navegador de consulta no consiguió recuperar `descenso.cl`; no se ha confirmado el estado de los endpoints publicados. No interpretar el código en GitHub como una confirmación de despliegue.

## Comprobación de activación sin credenciales

Visitar `https://descenso.cl/api/site-health` una vez desplegado.
El JSON solo muestra si los servicios están listos:

```json
{
  "service": "descenso-comments",
  "status": "setup_required",
  "checks": {
    "comments": "setup_required",
    "reports": "setup_required",
    "moderation": "setup_required"
  }
}
```

Este es **un ejemplo de estructura**, no una respuesta obtenida del sitio.
Si aparece `setup_required`, revisar el vínculo de D1, los secretos y `database/comments.sql`. Si aparece `ready`, realizar pruebas funcionales reales con autorización.
Si la URL responde 404, el despliegue no ha incorporado la función correspondiente.

## Renovación de despliegue desde GitHub

Cuando Cloudflare Pages no muestre **Reintentar implementación**, un commit nuevo en la rama `main` del repositorio conectado `descensocl-design/descenso-cl` puede activar automáticamente una nueva implementación de producción. Confirmar el resultado en **Workers y Pages > descenso-cl > Implementaciones**. Los secretos de producción deben estar guardados en el entorno correcto antes del despliegue.

<!-- Despliegue de configuración de secretos de Producción: 2026-11-10 posterior a MODERATION_TOKEN -->
