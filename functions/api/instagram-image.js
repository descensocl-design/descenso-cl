// Authorized JPEG uploads for Instagram drafts, stored in D1.
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json","cache-control":"no-store","x-content-type-options":"nosniff"}});
const validSlug=s=>typeof s==="string"&&/^20\d{2}-\d{2}-\d{2}-[a-z0-9-]{1,145}$/.test(s);
async function authorized(req,env){
 const auth=req.headers.get("authorization")||"";
 if(!env.MODERATION_TOKEN||env.MODERATION_TOKEN.length<32||!auth.startsWith("Bearer "))return false;
 const hash=async s=>new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s)));
 const [a,b]=await Promise.all([hash(auth.slice(7)),hash(env.MODERATION_TOKEN)]);
 let diff=0;for(let i=0;i<a.length;i++)diff|=a[i]^b[i];return diff===0;
}
const init=db=>db.prepare("CREATE TABLE IF NOT EXISTS social_ig_images (slug TEXT PRIMARY KEY, jpeg TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)").run();
export async function onRequestGet({request,env}){
 const slug=new URL(request.url).searchParams.get("slug");
 if(!validSlug(slug))return json({error:"Imagen inválida"},400);
 if(!env.COMMENTS_DB)return json({error:"Almacenamiento no disponible"},503);
 await init(env.COMMENTS_DB);
 const row=await env.COMMENTS_DB.prepare("SELECT jpeg FROM social_ig_images WHERE slug=?").bind(slug).first();
 if(!row)return json({error:"Imagen no encontrada"},404);
 const binary=atob(row.jpeg),bytes=new Uint8Array(binary.length);
 for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
 return new Response(bytes,{headers:{"content-type":"image/jpeg","cache-control":"public, max-age=300","x-content-type-options":"nosniff"}});
}
export async function onRequestPost({request,env}){
 if(!await authorized(request,env))return json({error:"No autorizado"},401);
 if(!env.COMMENTS_DB)return json({error:"Almacenamiento no disponible"},503);
 const origin=request.headers.get("origin");
 if(origin&&origin!==new URL(request.url).origin)return json({error:"Origen no permitido"},403);
 if(!(request.headers.get("content-type")||"").startsWith("application/json"))return json({error:"Formato inválido"},415);
 let data;try{data=await request.json()}catch{return json({error:"JSON inválido"},400)}
 if(!validSlug(data?.slug)||typeof data.jpeg!=="string"||data.jpeg.length>1300000||!/^[A-Za-z0-9+/]+={0,2}$/.test(data.jpeg))return json({error:"Imagen inválida o demasiado grande"},400);
 try{
  const header=atob(data.jpeg.slice(0,32));
  if(header.charCodeAt(0)!==255||header.charCodeAt(1)!==216||header.charCodeAt(2)!==255)return json({error:"Se requiere JPEG real"},400);
  await init(env.COMMENTS_DB);
  const published=await env.COMMENTS_DB.prepare("SELECT status FROM social_ig_posts WHERE slug=?").bind(data.slug).first().catch(()=>null);
  if(published&&["published","processing"].includes(published.status))return json({error:"No se puede modificar una publicación enviada"},409);
  await env.COMMENTS_DB.prepare("INSERT INTO social_ig_images (slug,jpeg) VALUES(?,?) ON CONFLICT(slug) DO UPDATE SET jpeg=excluded.jpeg,updated_at=CURRENT_TIMESTAMP").bind(data.slug,data.jpeg).run();
  return json({ok:true,url:new URL("/api/instagram-image?slug="+encodeURIComponent(data.slug),request.url).href});
 }catch{return json({error:"No se pudo almacenar la imagen"},503)}
}