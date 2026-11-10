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
