// Reportar abuso sin exponer la identidad ni el IP del denunciante.
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});
const normalizeSlug=v=>/^[a-z0-9-]{6,140}$/.test(String(v||""))?String(v):null;
async function hashVisitor(request,salt){
 const raw=(request.headers.get("CF-Connecting-IP")||"unknown")+":"+salt;
 const hash=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(raw));
 return Array.from(new Uint8Array(hash),x=>x.toString(16).padStart(2,"0")).join("");
}
export async function onRequestPost({request,env,params}){
 const slug=normalizeSlug(params.slug);
 if(!slug)return json({error:"Noticia inválida"},400);
 if(!env.COMMENTS_DB||!env.COMMENTS_SALT)return json({error:"Reportes no disponibles"},503);
 const origin=request.headers.get("Origin");
 if(origin){try{if(new URL(origin).origin!==new URL(request.url).origin)return json({error:"Origen inválido"},403)}catch{return json({error:"Origen inválido"},403)}}
 if((request.headers.get("content-type")||"").split(";")[0].trim()!=="application/json")return json({error:"Formato inválido"},415);
 if(Number(request.headers.get("content-length")||0)>1000)return json({error:"Solicitud demasiado grande"},413);
 let data;try{data=await request.json()}catch{return json({error:"Solicitud inválida"},400)}
 const id=typeof data.comment_id==="string"?data.comment_id:"";
 const reason=typeof data.reason==="string"?data.reason:"";
 if(!/^[a-f0-9-]{36}$/i.test(id)||!["spam","abuso","otro"].includes(reason))return json({error:"Reporte inválido"},400);
 try{
  const comment=await env.COMMENTS_DB.prepare("SELECT id FROM comments WHERE id=? AND article_slug=? AND status='approved'").bind(id,slug).first();
  if(!comment)return json({error:"Comentario no disponible"},404);
  const key=await hashVisitor(request,env.COMMENTS_SALT);
  await env.COMMENTS_DB.prepare("INSERT OR IGNORE INTO comment_reports (id,comment_id,article_slug,reporter_hash,reason,created_at) VALUES (?,?,?,?,?,?)")
   .bind(crypto.randomUUID(),id,slug,key,reason,new Date().toISOString()).run();
  return json({ok:true,message:"Reporte recibido. Gracias por avisarnos."});
 }catch{return json({error:"Los reportes aún no están configurados en D1"},503)}
}
