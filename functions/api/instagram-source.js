// Fetches image bytes for authorized editorial preview only. No open proxy.
const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json","cache-control":"no-store"}});
const allowed=u=>u.protocol==="https:"&&!u.username&&!u.password&&u.port===""&&["ep1.pinkbike.org","descenso.cl"].includes(u.hostname)&&/\.jpe?g$/i.test(u.pathname);
async function auth(req,env){
 const h=req.headers.get("authorization")||"";
 if(!env.MODERATION_TOKEN||env.MODERATION_TOKEN.length<32||!h.startsWith("Bearer "))return false;
 const hash=async v=>new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(v)));
 const [a,b]=await Promise.all([hash(h.slice(7)),hash(env.MODERATION_TOKEN)]);let d=0;for(let i=0;i<a.length;i++)d|=a[i]^b[i];return d===0;
}
export async function onRequestGet({request,env}){
 if(!await auth(request,env))return response({error:"No autorizado"},401);
 const raw=new URL(request.url).searchParams.get("url")||"";
 let url;try{url=new URL(raw)}catch{return response({error:"URL inválida"},400)}
 if(!allowed(url))return response({error:"Dominio de imagen no autorizado"},400);
 try{
  const r=await fetch(url.href,{redirect:"manual",headers:{"accept":"image/jpeg"}});
  if(!r.ok||r.status>=300)return response({error:"No se pudo recuperar la fotografía"},502);
  const type=r.headers.get("content-type")||"";
  if(!type.startsWith("image/jpeg"))return response({error:"La fuente no entregó JPEG"},415);
  if(Number(r.headers.get("content-length")||0)>8e6)return response({error:"Fotografía demasiado grande"},413);
  const bytes=await r.arrayBuffer();
  if(bytes.byteLength>8e6)return response({error:"Fotografía demasiado grande"},413);
  return new Response(bytes,{headers:{"content-type":"image/jpeg","cache-control":"private, no-store","x-content-type-options":"nosniff"}});
 }catch{return response({error:"Error al cargar fotografía"},502)}
}
