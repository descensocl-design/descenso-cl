// Cloudflare Pages Function — comentarios públicos con revisión editorial.
// Vincular una base D1 con nombre de binding COMMENTS_DB para activar el servicio.
const json = (data, status=200) => new Response(JSON.stringify(data), {
  status, headers: { "content-type":"application/json; charset=utf-8", "cache-control":"no-store", "x-content-type-options":"nosniff" }
});
function normalizeSlug(raw) {
  const value = String(raw || "").replace(/^\/+|\/+$/g, "");
  return /^[a-z0-9-]{6,140}$/.test(value) ? value : null;
}
async function visitorKey(request, secret) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const enc = new TextEncoder().encode(String(secret || "descenso") + ":" + ip);
  const hash = await crypto.subtle.digest("SHA-256", enc);
  return [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2,"0")).join("");
}
export async function onRequestGet({request, env, params}) {
  const slug = normalizeSlug(params.slug);
  if (!slug) return json({error:"Noticia inválida"},400);
  if (!env.COMMENTS_DB) return json({configured:false,comments:[]});
  try {
    const r = await env.COMMENTS_DB.prepare(
      "SELECT id, display_name, message, created_at FROM comments WHERE article_slug=? AND status='approved' ORDER BY created_at DESC LIMIT 100"
    ).bind(slug).all();
    return json({configured:true, comments:r.results || []});
  } catch(e) {
    return json({configured:false,comments:[],error:"No se ha preparado la base de datos de comentarios"});
  }
}
export async function onRequestPost({request, env, params}) {
  const slug = normalizeSlug(params.slug);
  if (!slug) return json({error:"Noticia inválida"},400);
  if (!env.COMMENTS_DB || !env.COMMENTS_SALT) return json({error:"Los comentarios aún no están configurados"},503);
  if ((request.headers.get("content-type")||"").split(";")[0].trim()!=="application/json") return json({error:"Formato inválido"},415);
  const origin = request.headers.get("Origin");
  if (origin && new URL(origin).hostname !== new URL(request.url).hostname) return json({error:"Origen no permitido"},403);
  const size = Number(request.headers.get("content-length")||0);
  if (size > 5000) return json({error:"Comentario demasiado largo"},413);
  let body;
  try {body = await request.json()}catch {return json({error:"JSON inválido"},400)}
  const anonymous = body.anonymous === true;
  const name = anonymous ? "Anónimo" : String(body.name || "").trim();
  const message = String(body.message || "").trim();
  if (name.length < 2 || name.length > 40 || message.length < 12 || message.length > 1500) return json({error:"El nombre debe tener entre 2 y 40 caracteres y el comentario entre 12 y 1500"},400);
  if (/https?:\/\/|www\.|<[^>]+>/i.test(message)) return json({error:"No se permiten enlaces ni HTML"},400);
  const key = await visitorKey(request, env.COMMENTS_SALT);
  const now = new Date().toISOString();
  try {
    const last = await env.COMMENTS_DB.prepare("SELECT created_at FROM comments WHERE visitor_hash=? ORDER BY created_at DESC LIMIT 1").bind(key).first();
    if (last && Date.now() - Date.parse(last.created_at) < 120000) return json({error:"Puedes enviar otro comentario después de dos minutos"},429);
    const lastDay = await env.COMMENTS_DB.prepare("SELECT COUNT(*) n FROM comments WHERE visitor_hash=? AND created_at>=?").bind(key, new Date(Date.now()-86400000).toISOString()).first();
    if (lastDay && lastDay.n >= 10) return json({error:"Límite diario de comentarios alcanzado"},429);
    const id = crypto.randomUUID();
    await env.COMMENTS_DB.prepare(
      "INSERT INTO comments (id, article_slug, display_name, message, status, visitor_hash, created_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)"
    ).bind(id, slug, name, message, key, now).run();
    return json({ok:true,pending:true,message:"Comentario recibido. Aparecerá tras la revisión editorial."},201);
  } catch(e) {return json({error:"No se pudo guardar el comentario"},503)}
}
