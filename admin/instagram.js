'use strict';
(() => {
  const $=id=>document.getElementById(id);
  let token='',posts=[],records=new Map(),selected=null,connected=false,busy=false,filter='pending';
  const slugify=value=>String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,85);
  const slug=p=>(p.permalink||('/noticias/'+p.date+'-'+slugify(p.title)+'/')).split('/').filter(Boolean).pop();
  const path=p=>p.permalink||('/noticias/'+slug(p)+'/');
  const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;};
  const info=text=>$('main-status').textContent=text;
  const state=text=>$('article-state').textContent=text;
  function captionFor(p){
    const category=String(p.category||'Mountain Bike').toUpperCase();
    const intro=String(p.excerpt||'').trim();
    return [String(p.title||'').trim(),'',intro,'','Lee la noticia completa en DESCENSO.CL. Enlace en la biografía.','','#DescensoCL #MountainBike #'+(category==='DOWNHILL'?'Downhill':category==='ENDURO'?'Enduro':'MTB')].join('\n').slice(0,2200);
  }
  async function api(init={}){
    const res=await fetch('/api/instagram',{...init,cache:'no-store',headers:{authorization:'Bearer '+token,...(init.headers||{})}});
    let data;try{data=await res.json()}catch{throw Error('El servidor no respondió correctamente');}
    if(!res.ok)throw Error(data.error||'Error de conexión');
    return data;
  }
  function currentRecord(){return selected?records.get(slug(selected)):null;}
  const statusOf=post=>records.get(slug(post))?.status||'prepared';
  const matchesFilter=post=>filter==='all'||
    (filter==='pending'&&!['published','dismissed'].includes(statusOf(post)))||
    (filter==='draft'&&statusOf(post)==='draft')||
    (filter==='published'&&statusOf(post)==='published')||
    (filter==='dismissed'&&statusOf(post)==='dismissed');
  function drawList(){
    const container=$('article-list');container.replaceChildren();
    const visible=posts.filter(matchesFilter);
    for(const post of visible){
      const id=slug(post),status=statusOf(post),button=node('button','insta-article');
      const label={published:'PUBLICADO',processing:'ENVIANDO',draft:'BORRADOR GUARDADO',failed:'REVISAR ERROR',dismissed:'DESCARTADO',prepared:'PREPARADO AUTOMÁTICAMENTE'}[status]||'PENDIENTE';
      button.type='button';button.setAttribute('aria-pressed',String(selected&&slug(selected)===id));
      button.append(node('span','',post.title),node('small','',post.date+' · '+label));
      button.addEventListener('click',()=>choose(post));
      container.append(button);
    }
    $('list-empty').hidden=visible.length!==0;
    const counts={pending:0,draft:0,published:0,dismissed:0,all:posts.length};
    for(const post of posts){
      const status=statusOf(post);
      if(!['published','dismissed'].includes(status))counts.pending++;
      if(status==='draft')counts.draft++;
      if(status==='published')counts.published++;
      if(status==='dismissed')counts.dismissed++;
    }
    for(const [key,count] of Object.entries(counts))$('count-'+key).textContent='('+count+')';
    $('workspace-count').textContent=counts.pending+' por revisar · '+counts.published+' publicadas';
  }
  function setButtons(){
    const record=currentRecord(),status=record?.status||'prepared';
    const published=status==='published',processing=status==='processing',dismissed=status==='dismissed';
    $('save').disabled=busy||!selected||published||processing||dismissed;
    $('publish').disabled=busy||!selected||!connected||published||dismissed;
    $('publish').textContent=processing?'COMPLETAR PUBLICACIÓN':published?'YA PUBLICADA':'APROBAR Y PUBLICAR';
    $('dismiss').disabled=busy||!selected||published||processing;
    $('dismiss').textContent=dismissed?'RESTAURAR PROPUESTA':'DESCARTAR PROPUESTA';
    $('caption').disabled=published||processing||dismissed;
    $('image-url').disabled=published||processing||dismissed;
    $('image-rights').disabled=published||processing||dismissed;
  }
  function choose(post){
    selected=post;
    $('editor-panel').hidden=!post;
    if(!post){drawList();return;}
    const id=slug(post),record=records.get(id);
    $('article-headline').textContent=post.title;
    $('article-link').href=path(post);
    const artwork='/assets/instagram/'+encodeURIComponent(id)+'.jpg';
    $('preview-title').textContent=post.title;
    $('caption').value=record?.caption||post.caption||captionFor(post);
    $('image-url').value=record?.image_url||post.image_url||new URL(artwork,location.origin).href;
    $('image-rights').checked=Boolean(record?.rights_confirmed);
    updatePreview();
    state(record?.status==='published'?'Esta noticia ya fue publicada en Instagram.':record?.status==='processing'?'Hay una publicación iniciada. Pulsa COMPLETAR PUBLICACIÓN.':record?.status==='dismissed'?'Propuesta descartada. Puedes restaurarla cuando quieras.':record?.error?record.error:record?.status==='draft'?'Borrador guardado. Revisa antes de publicar.':'Texto y portada preparados automáticamente. Revisa y aprueba para publicar.');
    drawList();setButtons();
  }
  function updatePreview(){
    $('preview-caption').textContent=$('caption').value.slice(0,370);
    $('char-count').textContent=$('caption').value.length+' / 2200';
    const image=$('image-url').value.trim();
    if(/^https:\/\/[^\s]+\.jpe?g(?:\?.*)?$/i.test(image))$('article-image').src=image;
  }
  function setFilter(next){
    filter=next;
    document.querySelectorAll('.insta-filters [data-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.filter===filter)));
    const available=posts.filter(matchesFilter);
    const choice=available.find(post=>selected&&slug(post)===slug(selected))||available[0]||null;
    choose(choice);
  }
  async function refresh(){
    const [news,proposals,server]=await Promise.all([
      fetch('/data/posts.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('No se pudo leer el catálogo de noticias');return r.json()}),
      fetch('/data/instagram-drafts.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
      api()
    ]);
    const catalog=Array.isArray(proposals)&&proposals.length?proposals:news;
    posts=catalog.filter(p=>p&&p.title&&p.date).sort((a,b)=>String(b.date).localeCompare(String(a.date)));
    records=new Map((server.posts||[]).map(r=>[r.slug,r]));
    connected=Boolean(server.meta_ready);
    $('connection-state').textContent=connected?'META CONFIGURADO · PUBLICACIÓN BAJO TU APROBACIÓN':'META PENDIENTE · BORRADORES ACTIVOS';
    $('workspace').hidden=false;$('access-form').hidden=true;
    setFilter(filter);
  }
  async function save(){
    if(!selected)return;
    const payload={action:'save',slug:slug(selected),caption:$('caption').value,image_url:$('image-url').value.trim(),rights_confirmed:$('image-rights').checked};
    if(payload.caption.trim().length<30)throw Error('Escribe un texto de al menos 30 caracteres.');
    if(payload.image_url&&!/^https:\/\/.+\.jpe?g(?:\?.*)?$/i.test(payload.image_url))throw Error('Usa una URL HTTPS que termine en .jpg o .jpeg.');
    const result=await api({method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
    records.set(payload.slug,{...payload,status:result.status});
    drawList();setButtons();state('Borrador guardado. Todavía no se ha publicado.');
  }
  async function beginPublish(){
    if(!selected||!connected)return;
    const id=slug(selected),existing=currentRecord();
    if(existing?.status!=='processing'){
      if(!$('image-rights').checked)throw Error('Confirma los derechos de la fotografía para Instagram antes de publicar.');
      if(!$('image-url').value.trim())throw Error('Especifica una fotografía JPEG autorizada para Instagram.');
      if(!confirm('¿Publicar esta noticia en @descenso.cl? La publicación será pública.'))return;
      await save();
      const result=await api({method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'start',slug:id})});
      records.set(id,{...records.get(id),status:result.status});
      state(result.message||'Publicación iniciada.');setButtons();drawList();
    }
    for(let retry=0;retry<12;retry++){
      if(retry)await new Promise(resolve=>setTimeout(resolve,2500));
      const result=await api({method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'finish',slug:id})});
      if(result.status==='published'){
        records.set(id,{...records.get(id),status:'published',instagram_id:result.instagram_id});
        state('PUBLICADO EN INSTAGRAM. ID: '+result.instagram_id);
        drawList();setButtons();info('Noticia publicada en @descenso.cl. La siguiente propuesta sigue esperando tu aprobación.');return;
      }
      state('Meta está procesando la fotografía… ('+(retry+1)+'/12)');
    }
    state('Meta sigue procesando. Puedes pulsar COMPLETAR PUBLICACIÓN para continuar más tarde.');
  }
  $('access-form').addEventListener('submit',async e=>{
    e.preventDefault();token=$('access-token').value.trim();$('access-token').value='';
    if(!token)return;
    try{
      info('Verificando clave de moderación…');
      const probe=await fetch('/api/instagram?auth=1',{headers:{authorization:'Bearer '+token},cache:'no-store'});
      const check=await probe.json().catch(()=>({}));
      if(!probe.ok)throw Error(probe.status===401?'Clave incorrecta. Usa MODERATION_TOKEN, la misma del panel de moderación de comentarios.':check.error||'No se pudo verificar la clave.');
      info('Clave correcta. Cargando base de datos…');
      await refresh();info('Acceso autorizado.');
    }catch(error){token='';info(error.message)}
  });
  $('logout').addEventListener('click',()=>{token='';posts=[];records.clear();selected=null;filter='pending';$('workspace').hidden=true;$('access-form').hidden=false;info('Sesión cerrada.');});
  document.querySelectorAll('.insta-filters [data-filter]').forEach(button=>button.addEventListener('click',()=>setFilter(button.dataset.filter)));
  $('reload-news').addEventListener('click',async()=>{try{info('Actualizando propuestas y estados…');await refresh();info('Propuestas actualizadas. No se ha publicado nada.')}catch(error){info(error.message)}});
  $('dismiss').addEventListener('click',async()=>{
    if(!selected||busy)return;
    const id=slug(selected),discarded=currentRecord()?.status==='dismissed';
    if(!discarded&&!confirm('¿Descartar esta propuesta? La noticia seguirá en la web y podrás restaurar el borrador.'))return;
    busy=true;setButtons();
    try{
      const result=await api({method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:discarded?'restore':'dismiss',slug:id})});
      records.set(id,{...records.get(id),status:result.status,rights_confirmed:0});
      setFilter(discarded?'pending':filter);
      info(discarded?'Propuesta restaurada. Revisa antes de publicar.':'Propuesta descartada sin publicar en Instagram.');
    }catch(error){state(error.message)}finally{busy=false;setButtons()}
  });
  $('caption').addEventListener('input',updatePreview);
  $('image-url').addEventListener('input',updatePreview);
  $('save').addEventListener('click',async()=>{busy=true;setButtons();try{await save()}catch(e){state(e.message)}finally{busy=false;setButtons()}});
  $('publish').addEventListener('click',async()=>{busy=true;setButtons();try{await beginPublish()}catch(e){state(e.message)}finally{busy=false;setButtons()}});
  $('test-meta').addEventListener('click',async()=>{
    const b=$('test-meta');b.disabled=true;info('Consultando la API de Meta sin publicar…');
    try{const verified=await (async()=>{const res=await fetch('/api/instagram?check=1',{headers:{authorization:'Bearer '+token},cache:'no-store'});const data=await res.json();if(!res.ok)throw Error(data.error||'Meta no respondió');return data})();
      $('connection-state').textContent='META RESPONDE · @'+verified.username+' · PERMISO DE PUBLICACIÓN AÚN SIN PROBAR';
      info('Identidad de Instagram verificada. No se publicó contenido.');
    }catch(error){info(error.message);$('connection-state').textContent='META · CONEXIÓN NO VERIFICADA';}finally{b.disabled=false;}
  });
  $('copy-caption').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('caption').value);state('Texto copiado.')}catch{state('No se pudo copiar automáticamente.')}});
})();