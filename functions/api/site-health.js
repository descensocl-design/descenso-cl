// Diagnóstico seguro y mínimo de servicios de Descenso.cl.
// No expone claves, nombres de D1, valores de configuración ni datos personales.
const respond = (value, status=200) => new Response(JSON.stringify(value),{
 status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}
});
export async function onRequestGet({env}){
 const comments=!!(env.COMMENTS_DB&&env.COMMENTS_SALT);
 let commentSchema=false,reportSchema=false;
 if(comments){
   try {await env.COMMENTS_DB.prepare("SELECT id FROM comments LIMIT 1").all();commentSchema=true;}catch{}
   try {await env.COMMENTS_DB.prepare("SELECT id FROM comment_reports LIMIT 1").all();reportSchema=true;}catch{}
 }
 const moderationSecret = typeof env.MODERATION_TOKEN==="string" ? env.MODERATION_TOKEN : "";
 // Informar únicamente si el secreto llega al Worker y cumple el mínimo; jamás mostrar su contenido.
 const moderationConfig = !moderationSecret ? "missing" : moderationSecret.length < 32 ? "too_short" : "valid";
 const statuses={
  comments:comments&&commentSchema?"ready":"setup_required",
  reports:comments&&commentSchema&&reportSchema?"ready":"setup_required",
  moderation:comments&&commentSchema&&reportSchema&&moderationConfig==="valid"?"ready":"setup_required"
 };
 const allReady=Object.values(statuses).every(s=>s==="ready");
 return respond({service:"descenso-comments",status:allReady?"ready":"setup_required",checks:statuses,moderation_secret_check:moderationConfig});
}
