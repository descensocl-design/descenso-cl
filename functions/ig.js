// Enlace permanente para la biografía de @descenso.cl.
// Dirige a la última noticia publicada desde el panel de Instagram.
// Hasta la primera publicación, dirige a la noticia editorial seleccionada.
const FALLBACK_SLUG = "2026-11-12-mas-peso-para-bajar-mas-rapido-la-paradoja-que-esta-cambiando-el-downhill";
const validSlug = (value) => typeof value === "string" && /^20\d{2}-\d{2}-\d{2}-[a-z0-9-]{8,160}$/.test(value);

export async function onRequestGet({ env }) {
  let slug = FALLBACK_SLUG;
  if (env.COMMENTS_DB) {
    try {
      const latest = await env.COMMENTS_DB.prepare(
        "SELECT slug FROM social_ig_posts WHERE status = 'published' AND published_at IS NOT NULL ORDER BY published_at DESC LIMIT 1"
      ).first();
      if (validSlug(latest?.slug)) slug = latest.slug;
    } catch {
      // El acceso público nunca debe depender de una migración de base de datos.
    }
  }
  return new Response(null, {
    status: 302,
    headers: {
      location: "https://descenso.cl/noticias/" + encodeURIComponent(slug) + "/",
      "cache-control": "no-store, max-age=0",
      "x-robots-tag": "noindex"
    }
  });
}
