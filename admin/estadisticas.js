'use strict';
(()=>{
const $=id=>document.getElementById(id);
let key='',stats=null,articles=new Map(),loading=false;
const fmt=n=>new Intl.NumberFormat('es-CL').format(Number(n)||0);
const status=s=>$('status').textContent=s;
const say=s=>$('comments-status').textContent=s;
const item=(tag,cls,value)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(value!==undefined)el.textContent=String(value);return el};
async function api(url,options={}){
  const res=await fetch(url,{...options,cache:'no-store',headers:{authorization:'Bearer '+key,...options.headers}});
  const data=await res.json().catch(()=>({}));
  if(!res.ok)throw Error(data.error||'No se pudo consultar el servidor');
  return data;
}
const titleOf=path=>articles.get(path)||path.split('/').filter(Boolean).pop()?.replace(/-+/g,' ')||path;
function rowList(id,rows,keyName,valueName,kind){
  const root=$(id);root.replaceChildren();
  if(!rows.length){root.append(item('p','rank-empty','Todavía no hay datos para este período.'));return;}
  const max=Math.max(1,...rows.map(r=>Number(r[valueName]||0)));
  rows.forEach((r,i)=>{
    const wrapper=item('div','rank-item');wrapper.append(item('span','rank-index',String(i+1).padStart(2,'0')));
    const title=kind==='page'?titleOf(r[keyName]):kind==='outbound'?({youtube:'YouTube',instagram:'Instagram',tiktok:'TikTok',whatsapp:'WhatsApp',other:'Otros sitios'}[r[keyName]]||r[keyName]):titleOf(r[keyName]);
    if(kind!=='outbound'){
      const link=item('a','',title);link.href=kind==='page'?r[keyName]:r[keyName];link.target='_blank';link.rel='noopener noreferrer';wrapper.append(link);
    }else wrapper.append(item('span','rank-name',title));
    wrapper.append(item('strong','',fmt(r[valueName])));
    const meter=item('div','rank-meter'),fill=item('div','rank-fill');fill.style.width=(100*(Number(r[valueName]||0)/max)).toFixed(1)+'%';meter.append(fill);wrapper.append(meter);root.append(wrapper);
  });
}
function drawChart(trend,days){
  const chart=$('daily-chart');chart.replaceChildren();
  const today=new Date();today.setUTCHours(0,0,0,0);
  const map=new Map();
  for(const r of trend){if(!map.has(r.day))map.set(r.day,{session:0,pageview:0});map.get(r.day)[r.kind]=Number(r.n||0)}
  let values=[];for(let i=days-1;i>=0;i--){const d=new Date(today);d.setUTCDate(d.getUTCDate()-i);const day=d.toISOString().slice(0,10);values.push({day,...(map.get(day)||{session:0,pageview:0})})}
  const max=Math.max(1,...values.map(x=>Math.max(x.pageview,x.session)));let hasData=false;
  for(const [i,x] of values.entries()){
    const d=item('div','day');d.title=x.day+' · '+fmt(x.pageview)+' vistas · '+fmt(x.session)+' sesiones';
    if(x.pageview||x.session)hasData=true;
    for(const [kind,css] of [['pageview','views'],['session','sessions']]){
      const bar=item('span','bar '+css);bar.style.height=(100*x[kind]/max).toFixed(1)+'%';d.append(bar);
    }
    if(i===0||i===values.length-1||days<=30&&i%7===0||days>30&&i%Math.ceil(days/6)===0){
      const tick=item('span','tick',x.day.slice(5).replace('-','/'));d.append(tick);
    }
    chart.append(d);
  }
  $('chart-empty').hidden=hasData;
}
function updateStats(d){
  stats=d;const s=d.summary;
  $('range-caption').textContent=d.from+' — '+d.through;
  for(const [node,value] of [['k-sessions',s.sessions],['k-pageviews',s.pageviews],['k-comments',s.comments],['k-articles',s.article_click],['k-outbound',s.outbound],['k-embeds',s.video_embed_load],['k-home',s.homepage]])$(node).textContent=fmt(value);
  const yt=(d.outbound||[]).find(x=>x.target==='youtube');
  $('k-youtube').textContent=fmt(yt?.clicks||0);
  $('pending-badge').textContent=fmt(s.pending_comments)+' PENDIENTES';
  $('comment-pending-summary').textContent=fmt(s.pending_comments)+' pendientes · '+fmt(s.visible_comments)+' publicados';
  drawChart(d.trend||[],d.days);
  rowList('top-articles',d.top_pages||[],'path','views','page');
  rowList('outbound-list',d.outbound||[],'target','clicks','outbound');
}
async function loadStats(){
  $('refresh').disabled=true;status('Actualizando estadísticas…');
  try{const data=await api('/api/stats?days='+encodeURIComponent($('period').value));updateStats(data);status('Datos actualizados.');}
  catch(e){status(e.message)}finally{$('refresh').disabled=false}
}
function linkFor(slug){return '/noticias/'+encodeURIComponent(slug)+'/';}
async function action(id,what){
  if(what==='delete'&&!confirm('¿ELIMINAR DEFINITIVAMENTE este comentario? También se borrarán sus reportes. Esta acción no se puede deshacer.'))return;
  if(what==='hide'&&!confirm('¿Ocultar este comentario de la web?'))return;
  const buttons=[...document.querySelectorAll('[data-comment-id]')];for(const b of buttons)if(b.dataset.commentId===id)b.disabled=true;
  try{
    await api('/api/moderation',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id,action:what})});
    say(what==='delete'?'Comentario eliminado definitivamente.':'Comentario actualizado.');
    await Promise.all([loadComments(false),loadStats()]);
  }catch(e){say(e.message);for(const b of buttons)if(b.dataset.commentId===id)b.disabled=false}
}
function buttonFor(id,label,what,cls){
  const b=item('button',cls||'',label);b.type='button';b.dataset.commentId=id;b.addEventListener('click',()=>action(id,what));return b;
}
function renderComments(comments){
  const root=$('comments-list');root.replaceChildren();
  if(!comments.length){root.append(item('p','rank-empty','No hay comentarios en esta categoría.'));return}
  for(const c of comments){
    const card=item('article','reader-card'),head=item('div','reader-head');
    head.append(item('strong','',c.display_name||'Anónimo'));
    const date=new Date(c.created_at);head.append(item('span','',Number.isNaN(date.getTime())?'':date.toLocaleString('es-CL')));
    card.append(head,item('p','',c.message||''));
    const meta=item('div','reader-meta');
    const link=item('a','',titleOf(linkFor(c.article_slug)));link.href=linkFor(c.article_slug);link.target='_blank';link.rel='noopener noreferrer';
    meta.append(link,item('span','',fmt(c.reports)+' denuncias'));
    card.append(meta);
    const controls=item('div','reader-actions');
    if(c.status==='pending'){controls.append(buttonFor(c.id,'APROBAR','approve','approve'),buttonFor(c.id,'RECHAZAR','hide'))}
    if(c.status==='approved')controls.append(buttonFor(c.id,'OCULTAR','hide'));
    if(c.status==='rejected')controls.append(buttonFor(c.id,'RESTAURAR','restore','approve'));
    controls.append(buttonFor(c.id,'ELIMINAR','delete','delete'));
    card.append(controls);root.append(card);
  }
}
async function loadComments(updateNotice=true){
  if(updateNotice)say('Consultando comentarios…');
  try{
    const view=$('comments-filter').value;
    const data=await api('/api/moderation?view='+encodeURIComponent(view));
    renderComments(data.comments||[]);
    if(updateNotice)say(fmt((data.comments||[]).length)+' comentarios cargados.');
  }catch(e){$('comments-list').replaceChildren();say(e.message)}
}
async function getCatalog(){
  try{
    const res=await fetch('/data/posts.json',{cache:'no-store'});
    if(!res.ok)return;
    const posts=await res.json();
    for(const p of posts){
      if(!p.title)continue;
      let path=p.permalink;
      if(!path){
        const t=String(p.title||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,85);
        path='/noticias/'+p.date+'-'+t+'/';
      }
      articles.set(path,p.title);
    }
  }catch{}
}
$('access-form').addEventListener('submit',async event=>{
  event.preventDefault();if(loading)return;
  key=$('private-key').value.trim();$('private-key').value='';
  if(!key)return;loading=true;status('Comprobando acceso…');
  try{
    await api('/api/stats?auth=1');
    $('access-form').hidden=true;$('dashboard').hidden=false;
    await getCatalog();
    await Promise.all([loadStats(),loadComments()]);
  }catch(e){key='';status(e.message)}finally{loading=false}
});
$('period').addEventListener('change',loadStats);
$('refresh').addEventListener('click',async()=>{await Promise.all([loadStats(),loadComments()])});
$('comments-filter').addEventListener('change',()=>loadComments());
$('reload-comments').addEventListener('click',()=>loadComments());
$('signout').addEventListener('click',()=>{
  key='';stats=null;articles.clear();$('dashboard').hidden=true;$('access-form').hidden=false;
  $('comments-list').replaceChildren();$('daily-chart').replaceChildren();status('Sesión cerrada.');
});
})();