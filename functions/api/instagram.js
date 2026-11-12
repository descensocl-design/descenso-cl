// Instagram editorial API, secured with MODERATION_TOKEN. No third-party posts without approval.
const reply=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","referrer-policy":"no-referrer"}});
const digest=async v=>new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(v)));
async function auth(request,env){
 const source=request.headers.get("authorization")||"";
 if(typeof env.MODERATION_TOKEN!=="string"||env.MODERATION_TOKEN.length<32||!source.startsWith("Bearer ")||source.length>600)return false;
 const [a,b]=await Promise.all([digest(source.slice(7)),digest(env.MODERATION_TOKEN)]);
 let diff=0;for(let i=0;i<a.length;i++)diff|=a[i]^b[i];
 return diff===0;
}
async function guard(request,env){
 if(!await auth(request,env))return reply({error:"Acceso privado no autorizado"},401);
 if(!env.COMMENTS_DB)return reply({error:"Base de datos D1 no vinculada"},503);
 if(request.method==="POST"){
   const origin=request.headers.get("origin");
   try{if(origin&&new URL(origin).origin!==new URL(request.url).origin)return reply({error:"Origen no permitido"},403)}catch{return reply({error:"Origen inválido"},403)}
   if(!(request.headers.get("content-type")||"").startsWith("application/json"))return reply({error:"Se requiere JSON"},415);
   if(Number(request.headers.get("content-length")||0)>12000)return reply({error:"Solicitud demasiado grande"},413);
 }
 return null;
}
async function init(db){
 await db.prepare("CREATE TABLE IF NOT EXISTS social_ig_posts (slug TEXT PRIMARY KEY, caption TEXT NOT NULL DEFAULT '', image_url TEXT NOT NULL DEFAULT '', rights_confirmed INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'draft', container_id TEXT, instagram_id TEXT, error TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, published_at TEXT)").run();
}
const validSlug=v=>typeof v==="string"&&v.length>8&&v.length<170&&/^20\d\d-\d\d-\d\d-[a-z0-9-]+$/.test(v);
function validImage(v){try{const u=new URL(v);return u.protocol==="https:"&&!u.username&&!u.password&&u.hostname!=="localhost"&&/\.jpe?g$/i.test(u.pathname)&&v.length<1000}catch{return false}}
// Meta Unified Login (system-user token with instagram_content_publish) uses Facebook Graph API.
const graph="https://graph.facebook.com/v25.0/";
const apiCredentials=env=>typeof env.INSTAGRAM_ACCESS_TOKEN==="string"&&env.INSTAGRAM_ACCESS_TOKEN.length>30&&typeof env.INSTAGRAM_USER_ID==="string"&&/^\d{5,25}$/.test(env.INSTAGRAM_USER_ID);
async function meta(url,params,token){
 const init={method:params?"POST":"GET",headers:{"authorization":"Bearer "+token}};
 if(params){init.headers["content-type"]="application/x-www-form-urlencoded";init.body=new URLSearchParams(params).toString()}
 const res=await fetch(url,init);let data={};try{data=await res.json()}catch{}
 if(!res.ok||data.error)throw new Error("Meta: "+String(data.error?.message||"Error HTTP "+res.status).slice(0,300));
 return data;
}
export async function onRequestGet({request,env}){
 const denied=await guard(request,env);if(denied)return denied;
 try{
   await init(env.COMMENTS_DB);
   const data=await env.COMMENTS_DB.prepare("SELECT slug,caption,image_url,rights_confirmed,status,instagram_id,error,updated_at,published_at FROM social_ig_posts ORDER BY updated_at DESC LIMIT 500").all();
   if(new URL(request.url).searchParams.get("check")==="1"){
     if(!apiCredentials(env))return reply({error:"Faltan las credenciales de Instagram en Cloudflare"},503);
     try{
       const profile=await meta(graph+encodeURIComponent(env.INSTAGRAM_USER_ID)+"?fields=id,username",null,env.INSTAGRAM_ACCESS_TOKEN);
       if(String(profile.id)!==String(env.INSTAGRAM_USER_ID))throw new Error("La cuenta consultada no coincide con el ID configurado");
       return reply({ok:true,meta_ready:true,profile_valid:true,username:String(profile.username||"")});
     }catch(error){return reply({error:"Meta no validó el acceso a Instagram: "+String(error.message).slice(0,240)},502)}
   }
   return reply({ok:true,meta_ready:apiCredentials(env),posts:data.results||[]});
 }catch{return reply({error:"No se pudo consultar D1"},503)}
}
export async function onRequestPost({request,env}){
 const denied=await guard(request,env);if(denied)return denied;
 let data;try{data=await request.json()}catch{return reply({error:"JSON inválido"},400)}
 if(!data||!validSlug(data.slug)||!["save","start","finish"].includes(data.action))return reply({error:"Datos inválidos"},400);
 try{
  const db=env.COMMENTS_DB;await init(db);
  const slug=data.slug;
  const current=await db.prepare("SELECT * FROM social_ig_posts WHERE slug=?").bind(slug).first();
  if(data.action==="save"){
   if(current&&current.status!=="draft"&&current.status!=="failed")return reply({error:"Esta publicación ya fue enviada a Meta y no puede editarse"},409);
   const caption=String(data.caption||"").trim();
   const image=String(data.image_url||"").trim();
   if(caption.length<30||caption.length>2200||image.length>1000)return reply({error:"Texto de 30 a 2200 caracteres requerido"},400);
   if(image&&!validImage(image))return reply({error:"La foto debe ser HTTPS y JPEG (.jpg)"},400);
   await db.prepare("INSERT INTO social_ig_posts (slug,caption,image_url,rights_confirmed,status,error,updated_at) VALUES(?,?,?,?, 'draft',NULL,CURRENT_TIMESTAMP) ON CONFLICT(slug) DO UPDATE SET caption=excluded.caption,image_url=excluded.image_url,rights_confirmed=excluded.rights_confirmed,status='draft',error=NULL,updated_at=CURRENT_TIMESTAMP").bind(slug,caption,image,data.rights_confirmed===true?1:0).run();
   return reply({ok:true,status:"draft"});
  }
  if(!current)return reply({error:"Guarda el borrador antes de publicar"},409);
  if(current.status==="published")return reply({error:"Esta noticia ya se publicó en Instagram"},409);
  if(!apiCredentials(env))return reply({error:"Falta conectar Instagram profesional a Meta API. Configura INSTAGRAM_ACCESS_TOKEN e INSTAGRAM_USER_ID en Cloudflare."},503);
  if(!current.rights_confirmed||!validImage(current.image_url))return reply({error:"Debes confirmar derechos y usar una fotografía JPEG autorizada"},409);
  if(data.action==="start"){
    if(current.container_id&&current.status==="processing")return reply({ok:true,status:"processing",message:"Contenedor pendiente; puedes continuar."});
    if(!["draft","failed"].includes(current.status))return reply({error:"Estado incompatible"},409);
    const lock=await db.prepare("UPDATE social_ig_posts SET status='processing',error=NULL,container_id=NULL,updated_at=CURRENT_TIMESTAMP WHERE slug=? AND status IN ('draft','failed')").bind(slug).run();
    if(!lock.meta?.changes)return reply({error:"Otra publicación está en proceso"},409);
    try{
      const created=await meta(graph+env.INSTAGRAM_USER_ID+"/media",{image_url:current.image_url,caption:current.caption,alt_text:"Noticia de mountain bike en Descenso.cl"},env.INSTAGRAM_ACCESS_TOKEN);
      if(!created.id)throw new Error("Meta no entregó identificador del contenedor");
      await db.prepare("UPDATE social_ig_posts SET container_id=? WHERE slug=? AND status='processing'").bind(String(created.id),slug).run();
      return reply({ok:true,status:"processing",message:"Imagen enviada a Meta. Preparando publicación."});
    }catch(e){await db.prepare("UPDATE social_ig_posts SET status='failed',error=? WHERE slug=?").bind(String(e.message).slice(0,400),slug).run();return reply({error:String(e.message)},502)}
  }
  if(current.status!=="processing"||!current.container_id)return reply({error:"No hay una publicación preparada"},409);
  try{
    const status=await meta(graph+encodeURIComponent(current.container_id)+"?fields=status_code",null,env.INSTAGRAM_ACCESS_TOKEN);
    if(["IN_PROGRESS","CREATED"].includes(status.status_code))return reply({ok:true,status:"processing",message:"Instagram sigue procesando la imagen."});
    if(status.status_code!=="FINISHED")throw new Error("Contenedor de Instagram: "+String(status.status_code||"estado desconocido"));
    const published=await meta(graph+env.INSTAGRAM_USER_ID+"/media_publish",{creation_id:current.container_id},env.INSTAGRAM_ACCESS_TOKEN);
    if(!published.id)throw new Error("Instagram no confirmó el ID de publicación");
    await db.prepare("UPDATE social_ig_posts SET status='published',instagram_id=?,error=NULL,published_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE slug=? AND status='processing'").bind(String(published.id),slug).run();
    return reply({ok:true,status:"published",instagram_id:String(published.id)});
  }catch(e){
    // Never retry media_publish automatically after an uncertain network failure: avoids duplicate Instagram posts.
    const message=String(e.message||"Error al publicar").slice(0,400);
    await db.prepare("UPDATE social_ig_posts SET error=?,updated_at=CURRENT_TIMESTAMP WHERE slug=?").bind(message,slug).run();
    return reply({error:message},502);
  }
 }catch{return reply({error:"Error del servicio de Instagram. Revisa Cloudflare."},503)}
}
