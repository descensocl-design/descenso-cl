// Contadores propios de Descenso.cl. No registra direcciones IP, cookies ni parámetros de URL.
// El hash de una sesión es anónimo y cambia cada día; únicamente estima sesiones.
const answer=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});
const pageOk=p=>p==="/"||/^\/noticias\/[a-z0-9-]{6,150}\/$/.test(p);
const dayUTC=()=>new Date().toISOString().slice(0,10);
async function keyFor(session,day,secret){
  const bytes=new TextEncoder().encode(day+":"+secret+":"+session);
  const hash=new Uint8Array(await crypto.subtle.digest("SHA-256",bytes));
  return [...hash].map(v=>v.toString(16).padStart(2,"0")).join("");
}
export async function onRequestPost({request,env}){
  if(!env.COMMENTS_DB||typeof env.COMMENTS_SALT!=="string"||env.COMMENTS_SALT.length<16)return answer({error:"Estadísticas no disponibles"},503);
  const u=new URL(request.url);
  const origin=request.headers.get("origin");
  if(origin&&origin!==u.origin)return answer({error:"Origen no permitido"},403);
  const site=request.headers.get("sec-fetch-site");
  if(site&&site!=="same-origin"&&site!=="same-site"&&site!=="none")return answer({error:"Origen no permitido"},403);
  if(!(request.headers.get("content-type")||"").startsWith("application/json"))return answer({error:"Formato incorrecto"},415);
  if(Number(request.headers.get("content-length")||0)>750)return answer({error:"Solicitud demasiado grande"},413);
  if(/bot|crawler|spider|headless|lighthouse|monitor|preview|uptime/i.test(request.headers.get("user-agent")||""))return answer({ok:true,ignored:true});
  let event;try{event=await request.json()}catch{return answer({error:"JSON inválido"},400)}
  if(!event||!["pageview","outbound","article_click","video_embed_load"].includes(event.type))return answer({error:"Evento inválido"},400);
  const path=String(event.path||"");
  if(!pageOk(path))return answer({error:"Ruta inválida"},400);
  let target="-";
  if(event.type==="video_embed_load"){
    if(event.target!=="youtube")return answer({error:"Destino inválido"},400);
    target="youtube";
  }else if(event.type==="outbound"){
    if(!["youtube","instagram","tiktok","whatsapp","other"].includes(event.target))return answer({error:"Destino inválido"},400);
    target=event.target;
  }else if(event.type==="article_click"){
    target=String(event.target||"");
    if(!/^\/noticias\/[a-z0-9-]{6,150}\/$/.test(target)||path!=="/")return answer({error:"Destino inválido"},400);
  }
  const session=String(event.session||"");
  if(event.type==="pageview"&&!/^[a-zA-Z0-9_-]{16,72}$/.test(session))return answer({error:"Sesión inválida"},400);
  const day=dayUTC();
  try{
    if(event.type==="pageview"){
      const hash=await keyFor(session,day,env.COMMENTS_SALT);
      const unique=await env.COMMENTS_DB.prepare("INSERT OR IGNORE INTO web_stats_sessions(day,session_hash) VALUES(?,?)").bind(day,hash).run();
      if(unique.meta?.changes){
        await env.COMMENTS_DB.prepare("INSERT INTO web_stats_daily(day,kind,path,target,n) VALUES(?,'session','/','-',1) ON CONFLICT(day,kind,path,target) DO UPDATE SET n=n+1").bind(day).run();
      }
    }
    await env.COMMENTS_DB.prepare("INSERT INTO web_stats_daily(day,kind,path,target,n) VALUES(?,?,?,?,1) ON CONFLICT(day,kind,path,target) DO UPDATE SET n=n+1").bind(day,event.type,path,target).run();
    return answer({ok:true},202);
  }catch(e){
    // Si falta la migración, no interrumpir la navegación pública.
    return answer({error:"No se pudieron guardar las estadísticas"},503);
  }
}
