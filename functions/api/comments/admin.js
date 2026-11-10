// Cloudflare Pages Function: administración privada de comentarios.
const respond = (v, code=200) => new Response(JSON.stringify(v), {status:code,headers:{"content-type":"application/json;charset=utf-8","cache-control":"no-store"}});
function authorized(request,env) {
  const provided=request.headers.get("authorization")||"";
  return Boolean(env.COMMENTS_ADMIN_TOKEN && provided === "Bearer "+env.COMMENTS_ADMIN_TOKEN);
}
export async function onRequestGet({request,env}){
  if(!authorized(request,env)) return respond({error:"No autorizado"},401);
  if(!env.COMMENTS_DB) return respond({error:"Base de datos no configurada"},503);
  try {
    const r=await env.COMMENTS_DB.prepare("SELECT id,article_slug,display_name,message,status,created_at FROM comments WHERE status='pending' ORDER BY created_at DESC LIMIT 100").all();
    return respond({comments:r.results||[]});
  }catch(e){return respond({error:"Error de base de datos"},503)}
}
export async function onRequestPost({request,env}){
  if(!authorized(request,env)) return respond({error:"No autorizado"},401);
  if(!env.COMMENTS_DB) return respond({error:"Base de datos no configurada"},503);
  let data;try{data=await request.json()}catch{return respond({error:"Datos inválidos"},400)}
  if(typeof data.id!=="string" || !/^[a-f0-9-]{36}$/.test(data.id) || !["approved","rejected"].includes(data.status))return respond({error:"Datos inválidos"},400);
  try{
    const out=await env.COMMENTS_DB.prepare("UPDATE comments SET status=? WHERE id=? AND status='pending'").bind(data.status,data.id).run();
    return respond({ok:true,changed:out.meta?.changes||0});
  }catch(e){return respond({error:"Error al moderar"},503)}
}
