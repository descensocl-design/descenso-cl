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
