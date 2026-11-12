'use strict';
(() => {
  const $=id=>document.getElementById(id);
  let token='',posts=[],records=new Map(),selected=null,connected=false,busy=false;
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
  function drawList(){
    const container=$('article-list');container.replaceChildren();
    for(const post of posts){
      const id=slug(post),record=records.get(id),button=node('button','insta-article');
      button.type='button';button.setAttribute('aria-pressed',String(selected&&slug(selected)===id));
      button.append(node('span','',post.title),node('small','',post.date+' · '+(record?.status==='published'?'PUBLICADO':record?.status==='processing'?'ENVIANDO':record?.status==='draft'?'BORRADOR':record?.status==='failed'?'REVISAR ERROR':'PENDIENTE')));
      button.addEventListener('click',()=>choose(post));
      container.append(button);
    }
  }
  function setButtons(){
    const record=currentRecord(),published=record?.status==='published',processing=record?.status==='processing';
    $('save').disabled=busy||!selected||published||processing;
    $('publish').disabled=busy||!selected||!connected||published;
    $('publish').textContent=processing?'COMPLETAR PUBLICACIÓN':published?'YA PUBLICADA':'PUBLICAR EN INSTAGRAM';
    $('caption').disabled=published||processing;
    $('image-url').disabled=published||processing;
    $('image-rights').disabled=published||processing;
  }
  function choose(post){
    selected=post;const id=slug(post),record=records.get(id);
    $('article-headline').textContent=post.title;
    $('article-link').href=path(post);
    const artwork='/assets/instagram/'+encodeURIComponent(id)+'.jpg';
    $('article-image').src=artwork;
    $('preview-title').textContent=post.title;
    $('caption').value=record?.caption||captionFor(post);
    $('image-url').value=record?.image_url||new URL(artwork,location.origin).href;
    $('image-rights').checked=Boolean(record?.rights_confirmed);
    updatePreview();
    state(record?.status==='published'?'Esta noticia ya fue publicada en Instagram.':record?.status==='processing'?'Hay una publicación iniciada. Pulsa COMPLETAR PUBLICACIÓN.':record?.error?record.error:'Borrador pendiente de revisión.');
    drawList();setButtons();
  }
  function updatePreview(){
    $('preview-caption').textContent=$('caption').value.slice(0,370);
    $('char-count').textContent=$('caption').value.length+' / 2200';
  }
  async function refresh(){
    const [news,server]=await Promise.all([fetch('/data/posts.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('No se pudo leer el catálogo');return r.json()}),api()]);
    posts=news.filter(p=>p&&p.title&&p.date).sort((a,b)=>String(b.date).localeCompare(String(a.date)));
    records=new Map((server.posts||[]).map(r=>[r.slug,r]));
    connected=Boolean(server.meta_ready);
    $('connection-state').textContent=connected?'META CONECTADO · PUBLICACIÓN DISPONIBLE':'META PENDIENTE · BORRADORES ACTIVOS';
    $('workspace-count').textContent=posts.length+' noticias disponibles';
    choose(posts.find(p=>selected&&slug(p)===slug(selected))||posts[0]||null);
    $('workspace').hidden=false;$('access-form').hidden=true;
  }
  async function save(){
    if(!selected)return;
    const payload={action:'save',slug:slug(selected),caption:$('caption').value,image_url:$('image-url').value.trim(),rights_confirmed:$('image-rights').checked};
    if(payload.caption.trim().length<30)throw Error('Escribe un texto de al menos 30 caracteres.');
    if(payload.image_url&&!/^https:\/\/.+\.jpe?g(?:\?.*)?$/i.test(payload.image_url))throw Error('Usa una URL HTTPS que termine en .jpg o .jpeg.');
    const result=await api({method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
    records.set(payload.slug,{...payload,status:result.status});
    drawList();setButtons();state('Borrador guardado en D1. Todavía no se ha publicado.');
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
        drawList();setButtons();return;
      }
      state('Meta está procesando la fotografía… ('+(retry+1)+'/12)');
    }
    state('Meta sigue procesando. Puedes pulsar COMPLETAR PUBLICACIÓN para continuar más tarde.');
  }
  $('access-form').addEventListener('submit',async e=>{
    e.preventDefault();token=$('access-token').value.trim();$('access-token').value='';
    if(!token)return;
    try{info('Comprobando acceso…');await refresh();info('Acceso autorizado.');}
    catch(error){token='';info(error.message)}
  });
  $('logout').addEventListener('click',()=>{token='';posts=[];records.clear();selected=null;$('workspace').hidden=true;$('access-form').hidden=false;info('Sesión cerrada.');});
  $('caption').addEventListener('input',updatePreview);
  $('save').addEventListener('click',async()=>{busy=true;setButtons();try{await save()}catch(e){state(e.message)}finally{busy=false;setButtons()}});
  $('publish').addEventListener('click',async()=>{busy=true;setButtons();try{await beginPublish()}catch(e){state(e.message)}finally{busy=false;setButtons()}});
  $('copy-caption').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('caption').value);state('Texto copiado.')}catch{state('No se pudo copiar automáticamente.')}});
})();