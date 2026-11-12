// API de moderación de comentarios. Requiere MODERATION_TOKEN en secretos de Cloudflare Pages.
const respond=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","referrer-policy":"no-referrer"}});
const validId=id=>typeof id==="string"&&/^[0-9a-f-]{36}$/i.test(id);
async function fingerprint(text){
 const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));
 return new Uint8Array(digest);
}
async function authorized(req,env){
 if(!env.MODERATION_TOKEN||String(env.MODERATION_TOKEN).length<32)return false;
 const raw=req.headers.get("authorization")||"";
 if(!raw.startsWith("Bearer "))return false;
 const supplied=raw.slice(7);
 if(supplied.length>512)return false;
 const [a,b]=await Promise.all([fingerprint(supplied),fingerprint(env.MODERATION_TOKEN)]);
 let difference=0;for(let i=0;i<a.length;i++)difference|=a[i]^b[i];
 return difference===0;
}
async function guard(request,env){
 if(!env.COMMENTS_DB)return respond({error:"No hay base D1 vinculada"},503);
 if(!(await authorized(request,env)))return respond({error:"Acceso no autorizado"},401);
 if(request.method==="POST"){
   const origin=request.headers.get("Origin");
   if(origin){try{if(new URL(origin).origin!==new URL(request.url).origin)return respond({error:"Origen inválido"},403)}catch{return respond({error:"Origen inválido"},403)}}
 }
 return null;
}
export async function onRequestGet({request,env}){
 const denied=await guard(request,env);if(denied)return denied;
 try{
   const url=new URL(request.url),view=url.searchParams.get("view")||"reported";
   if(!["reported","recent","hidden","pending"].includes(view))return respond({error:"Filtro inválido"},400);
   let sql;
   if(view==="reported"){
     sql="SELECT c.id,c.article_slug,c.display_name,c.message,c.created_at,c.status,COUNT(r.id) AS reports,MAX(r.created_at) AS last_reported FROM comment_reports r JOIN comments c ON c.id=r.comment_id WHERE c.status='approved' GROUP BY c.id ORDER BY reports DESC,last_reported DESC LIMIT 100";
   }else{
     sql="SELECT c.id,c.article_slug,c.display_name,c.message,c.created_at,c.status,COUNT(r.id) AS reports FROM comments c LEFT JOIN comment_reports r ON c.id=r.comment_id WHERE c.status='"+(view==="hidden"?"rejected":view==="pending"?"pending":"approved")+"' GROUP BY c.id ORDER BY c.created_at DESC LIMIT 100";
   }
   const result=await env.COMMENTS_DB.prepare(sql).all();
   return respond({ok:true,view,comments:result.results||[]});
 }catch{return respond({error:"No se pudo leer la moderación. Revisa las tablas D1."},503)}
}
export async function onRequestPost({request,env}){
 const denied=await guard(request,env);if(denied)return denied;
 if((request.headers.get("content-type")||"").split(";")[0].trim()!=="application/json")return respond({error:"Formato inválido"},415);
 if(Number(request.headers.get("content-length")||0)>1000)return respond({error:"Solicitud demasiado grande"},413);
 let data;try{data=await request.json()}catch{return respond({error:"JSON inválido"},400)}
 if(!validId(data.id)||!["hide","restore","approve","delete"].includes(data.action))return respond({error:"Solicitud inválida"},400);
 try{
   const existing=await env.COMMENTS_DB.prepare("SELECT status FROM comments WHERE id=?").bind(data.id).first();
   if(!existing)return respond({error:"Comentario no encontrado"},404);
   if(data.action==="delete"){
     await env.COMMENTS_DB.batch([
       env.COMMENTS_DB.prepare("DELETE FROM comment_reports WHERE comment_id=?").bind(data.id),
       env.COMMENTS_DB.prepare("DELETE FROM comments WHERE id=?").bind(data.id)
     ]);
     return respond({ok:true,status:"deleted"});
   }
   if(data.action==="approve"&&existing.status!=="pending")return respond({error:"Solo se pueden aprobar comentarios pendientes"},409);
   if(data.action==="restore"&&existing.status!=="rejected")return respond({error:"El comentario no está oculto"},409);
   const status=data.action==="hide"?"rejected":"approved";
   await env.COMMENTS_DB.prepare("UPDATE comments SET status=? WHERE id=?").bind(status,data.id).run();
   return respond({ok:true,status});
 }catch{return respond({error:"No se pudo guardar el cambio"},503)}
}
