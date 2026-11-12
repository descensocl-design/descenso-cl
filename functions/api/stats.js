// Panel privado de estadísticas. Misma credencial que moderación (MODERATION_TOKEN).
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","referrer-policy":"no-referrer"}});
async function isAuthorized(request,env){
  const raw=request.headers.get("authorization")||"";
  if(!raw.startsWith("Bearer ")||raw.length>600||!env.MODERATION_TOKEN||env.MODERATION_TOKEN.length<32)return false;
  const enc=new TextEncoder();
  const [a,b]=await Promise.all([crypto.subtle.digest("SHA-256",enc.encode(raw.slice(7))),crypto.subtle.digest("SHA-256",enc.encode(env.MODERATION_TOKEN))]);
  const x=new Uint8Array(a),y=new Uint8Array(b);let difference=0;
  for(let i=0;i<x.length;i++)difference|=x[i]^y[i];
  return difference===0;
}
const rows=query=>query.results||[];
export async function onRequestGet({request,env}){
  if(!await isAuthorized(request,env))return json({error:"Clave privada incorrecta"},401);
  if(!env.COMMENTS_DB)return json({error:"La base de datos no está conectada"},503);
  if(new URL(request.url).searchParams.get("auth")==="1")return json({ok:true,authorized:true});
  const selected=Number(new URL(request.url).searchParams.get("days")||30);
  if(![7,30,90,365].includes(selected))return json({error:"Período inválido"},400);
  const from=new Date(Date.now()-(selected-1)*86400000).toISOString().slice(0,10);
  const db=env.COMMENTS_DB;
  try{
    // Reparación segura si el proyecto se despliega en una base D1 aún sin migrar.
    await db.prepare("CREATE TABLE IF NOT EXISTS web_stats_daily (day TEXT NOT NULL,kind TEXT NOT NULL,path TEXT NOT NULL,target TEXT NOT NULL,n INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(day,kind,path,target))").run();
    await db.prepare("CREATE TABLE IF NOT EXISTS web_stats_sessions (day TEXT NOT NULL,session_hash TEXT NOT NULL,PRIMARY KEY(day,session_hash))").run();
    const [totals,trend,topPages,outbound,articleClicks,commentTotals,commentTrend,commentTop]=await Promise.all([
      db.prepare("SELECT kind,SUM(n) AS total FROM web_stats_daily WHERE day>=? GROUP BY kind").bind(from).all(),
      db.prepare("SELECT day,kind,SUM(n) AS n FROM web_stats_daily WHERE day>=? AND kind IN ('session','pageview','outbound') GROUP BY day,kind ORDER BY day ASC").bind(from).all(),
      db.prepare("SELECT path,SUM(n) AS views FROM web_stats_daily WHERE day>=? AND kind='pageview' AND path LIKE '/noticias/%' GROUP BY path ORDER BY views DESC LIMIT 20").bind(from).all(),
      db.prepare("SELECT target,SUM(n) AS clicks FROM web_stats_daily WHERE day>=? AND kind='outbound' GROUP BY target ORDER BY clicks DESC").bind(from).all(),
      db.prepare("SELECT target,SUM(n) AS clicks FROM web_stats_daily WHERE day>=? AND kind='article_click' GROUP BY target ORDER BY clicks DESC LIMIT 10").bind(from).all(),
      db.prepare("SELECT COUNT(*) AS total,SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS visible,SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS hidden,SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending FROM comments WHERE substr(created_at,1,10)>=?").bind(from).first(),
      db.prepare("SELECT substr(created_at,1,10) AS day,COUNT(*) AS n FROM comments WHERE substr(created_at,1,10)>=? GROUP BY substr(created_at,1,10) ORDER BY day ASC").bind(from).all(),
      db.prepare("SELECT article_slug,COUNT(*) AS comments FROM comments WHERE substr(created_at,1,10)>=? GROUP BY article_slug ORDER BY comments DESC LIMIT 10").bind(from).all()
    ]);
    const summary={sessions:0,pageviews:0,outbound:0,article_click:0,video_embed_load:0};
    for(const entry of rows(totals))if(Object.hasOwn(summary,entry.kind))summary[entry.kind]=Number(entry.total||0);
    const homepage=await db.prepare("SELECT SUM(n) AS n FROM web_stats_daily WHERE day>=? AND kind='pageview' AND path='/'").bind(from).first();
    const reports=await db.prepare("SELECT COUNT(*) AS n FROM comment_reports WHERE substr(created_at,1,10)>=?").bind(from).first();
    return json({
      ok:true,days:selected,from,through:new Date().toISOString().slice(0,10),
      summary:{...summary,homepage:Number(homepage?.n||0),comments:Number(commentTotals?.total||0),visible_comments:Number(commentTotals?.visible||0),hidden_comments:Number(commentTotals?.hidden||0),pending_comments:Number(commentTotals?.pending||0),comment_reports:Number(reports?.n||0)},
      trend:rows(trend),top_pages:rows(topPages),outbound:rows(outbound),article_clicks:rows(articleClicks),
      comments_trend:rows(commentTrend),comment_top:rows(commentTop),
      notes:{visitors:"Sesiones aproximadas, no personas únicas: un navegador por día puede contar más de una vez.",youtube:"Se miden los clics a enlaces externos de YouTube y las cargas de reproductores integrados. No equivalen a reproducciones verificadas en YouTube.",history:"Las mediciones de visitas y clics comienzan desde la activación del contador."}
    });
  }catch(e){return json({error:"No se pudieron consultar las estadísticas. Comprueba que estén creadas las tablas en D1."},503)}
}
