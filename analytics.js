/* Descenso.cl: estadísticas opcionales, sin identificadores ficticios.
   Editar data/analytics-config.json antes de activar servicios externos. */
(async function(){
  try{
    const res=await fetch('/data/analytics-config.json',{cache:'no-store'});
    if(!res.ok)return;
    const config=await res.json();
    if(config?.cloudflare_web_analytics_token && /^[a-zA-Z0-9_-]{20,120}$/.test(config.cloudflare_web_analytics_token)){
      const script=document.createElement('script');
      script.defer=true;
      script.src='https://static.cloudflareinsights.com/beacon.min.js';
      script.dataset.cfBeacon=JSON.stringify({token:config.cloudflare_web_analytics_token});
      document.head.append(script);
    }
  }catch(error){/* La ausencia de estadísticas no afecta la lectura. */}
})();


/* Conteo agregado propio: no se guardan IP, cookies de rastreo ni identificadores de personas.
   Las cifras comienzan al desplegarse el servicio y son estimaciones, no Google Analytics. */
(() => {
  'use strict';
  if(navigator.doNotTrack==='1'||navigator.globalPrivacyControl===true)return;
  const path=location.pathname==='/'?'/':location.pathname.replace(/\/?$/,'/');
  if(path!=='/'&&!/^\/noticias\/[a-z0-9-]{6,150}\/$/.test(path))return;
  const key='descenso_stats_session_v1';
  let session;
  try{
    session=sessionStorage.getItem(key);
    if(!session){session=crypto.randomUUID().replace(/-/g,'');sessionStorage.setItem(key,session);}
  }catch{
    session=crypto.randomUUID().replace(/-/g,'');
  }
  function send(type,target){
    const payload={type,path,session};
    if(target)payload.target=target;
    fetch('/api/track',{
      method:'POST',cache:'no-store',keepalive:true,
      headers:{'content-type':'application/json'},
      body:JSON.stringify(payload)
    }).catch(()=>{});
  }
  send('pageview');
  document.addEventListener('click',event=>{
    const a=event.target.closest('a[href]');
    if(!a)return;
    let url;try{url=new URL(a.href,location.href)}catch{return}
    if(url.origin===location.origin){
      const destination=url.pathname.replace(/\/?$/,'/');
      if(path==='/'&&/^\/noticias\/[a-z0-9-]{6,150}\/$/.test(destination))send('article_click',destination);
      return;
    }
    if(!/^https?:$/.test(url.protocol))return;
    const host=url.hostname.toLowerCase();
    const target=host==='youtu.be'||host==='youtube.com'||host.endsWith('.youtube.com')?'youtube':
      host==='instagram.com'||host.endsWith('.instagram.com')?'instagram':
      host==='tiktok.com'||host.endsWith('.tiktok.com')?'tiktok':
      host==='whatsapp.com'||host.endsWith('.whatsapp.com')||host==='wa.me'?'whatsapp':'other';
    send('outbound',target);
  },{capture:true});
  const observed=new WeakSet();
  function observeFrames(){
    document.querySelectorAll('iframe[src]').forEach(frame=>{
      if(observed.has(frame))return;
      let host='';try{host=new URL(frame.src).hostname}catch{}
      if(!/^(www\.)?(youtube-nocookie\.com|youtube\.com)$/.test(host))return;
      observed.add(frame);
      frame.addEventListener('load',()=>send('video_embed_load','youtube'),{once:true});
    });
  }
  observeFrames();
  const observer=new MutationObserver(observeFrames);
  observer.observe(document.body,{subtree:true,childList:true});
  window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
})();
