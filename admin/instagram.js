'use strict';
(() => {
  const $=id=>document.getElementById(id);
  let token='',posts=[],records=new Map(),selected=null,connected=false,busy=false,filter='pending',uncertainPublish=false,sourcePhotos=[],layoutIndex=0;
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
    let res;
    try{
      res=await fetch('/api/instagram',{...init,cache:'no-store',headers:{authorization:'Bearer '+token,...(init.headers||{})}});
    }catch(error){
      throw Error('No fue posible conectar con el servidor. No reintentes publicar antes de comprobar el estado en Instagram.');
    }
    const raw=await res.text();
    let data;
    try{data=JSON.parse(raw)}catch{
      const ray=(res.headers.get('cf-ray')||'').split('-')[0].slice(0,20);
      const status='HTTP '+res.status;
      console.error('Instagram: respuesta no JSON del servidor',{status:res.status,contentType:res.headers.get('content-type'),ray,bodyStart:raw.slice(0,160)});
      throw Error('Cloudflare devolvió una respuesta inesperada ('+status+(ray?', ref. '+ray:'')+'). No vuelvas a publicar todavía: comprueba el estado en Instagram y actualiza las propuestas.');
    }
    if(!res.ok)throw Error(data.error||('Error del servidor (HTTP '+res.status+')'));
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
    $('publish').disabled=busy||uncertainPublish||!selected||!connected||published||dismissed;
    $('publish').textContent=uncertainPublish?'VERIFICAR ESTADO ANTES':processing?'COMPLETAR PUBLICACIÓN':published?'YA PUBLICADA':'APROBAR Y PUBLICAR';
    $('dismiss').disabled=busy||!selected||published||processing;
    $('dismiss').textContent=dismissed?'RESTAURAR PROPUESTA':'DESCARTAR PROPUESTA';
    $('caption').disabled=published||processing||dismissed;
    $('image-url').disabled=published||processing||dismissed;
    $('image-rights').disabled=published||processing||dismissed;
    $('image-upload').disabled=busy||published||processing||dismissed;
    $('generate-cover').disabled=busy||published||processing||dismissed;
    $('regenerate-cover').disabled=busy||published||processing||dismissed;
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
    $('image-url').value=record?.image_url||post.image_url||'';
    $('image-rights').checked=Boolean(record?.rights_confirmed);
    $('image-upload').value='';$('upload-status').textContent='Puedes reemplazar la portada automática por una fotografía propia o autorizada.';
    updatePreview();
    loadSources(post);
    state(record?.status==='published'?'Esta noticia ya fue publicada en Instagram.':record?.status==='processing'?'Hay una publicación iniciada. Pulsa COMPLETAR PUBLICACIÓN.':record?.status==='dismissed'?'Propuesta descartada. Puedes restaurarla cuando quieras.':record?.error?record.error:record?.status==='draft'?'Borrador guardado. Revisa antes de publicar.':post.cover_preview_url?'Noticia cargada. Selecciona las fotos de la galería y genera una portada; aún no se ha publicado.':'Texto y portada preparados automáticamente. Revisa y aprueba para publicar.');
    drawList();setButtons();
  }
  function updatePreview(){
    $('preview-caption').textContent=$('caption').value.slice(0,370);
    $('char-count').textContent=$('caption').value.length+' / 2200';
    const image=$('image-url').value.trim();
    if(/^https:\/\//i.test(image))$('article-image').src=image;
    else if(/^https:\/\//i.test(selected?.cover_preview_url||''))$('article-image').src=selected.cover_preview_url;
    else $('article-image').removeAttribute('src');
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
    if(payload.image_url&&!/^https:\/\//i.test(payload.image_url))throw Error('Usa una URL HTTPS que termine en .jpg o .jpeg.');
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
  $('reload-news').addEventListener('click',async()=>{try{info('Actualizando propuestas y estados…');await refresh();uncertainPublish=false;setButtons();info('Estados consultados. Comprueba también la cuenta de Instagram antes de volver a publicar.')}catch(error){info(error.message)}});
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

  async function loadSources(post){
    const host=$('source-photos');sourcePhotos=[];host.replaceChildren();
    $('generator-status').textContent='Cargando fotografías de la noticia…';
    const fallback=slug(post)==='2026-11-17-joyas-del-downhill-balfa-devinci-restauradas'
      ? ['https://ep1.pinkbike.org/p5pb30529364/p5pb30529364.jpg','https://ep1.pinkbike.org/p5pb30529395/p5pb30529395.jpg','https://ep1.pinkbike.org/p5pb30529396/p5pb30529396.jpg','https://ep1.pinkbike.org/p5pb30529387/p5pb30529387.jpg','https://ep1.pinkbike.org/p5pb30529397/p5pb30529397.jpg'] : [];
    function render(urls){
      if(selected!==post)return;
      host.replaceChildren();sourcePhotos=urls.map(url=>({url,selected:false}));
      for(const item of sourcePhotos){
        const label=node('label','source-photo'),img=node('img'),check=node('input');
        img.alt='Fotografía original de la noticia';img.loading='lazy';img.src=item.url;
        img.onerror=async()=>{img.onerror=null;try{const res=await fetch('/api/instagram-source?url='+encodeURIComponent(item.url),{headers:{authorization:'Bearer '+token}});if(res.ok)img.src=URL.createObjectURL(await res.blob())}catch{}};
        check.type='checkbox';check.checked=false;check.addEventListener('change',()=>item.selected=check.checked);
        label.append(img,check);host.append(label);
      }
      $('generator-status').textContent=urls.length+' fotografías encontradas. Selecciona las que tengas autorización para publicar.';
    }
    if(fallback.length)render(fallback);
    try{
      const res=await fetch(path(post),{cache:'no-store'});if(!res.ok)throw Error('No se pudo leer la noticia');
      const doc=new DOMParser().parseFromString(await res.text(),'text/html');
      const urls=[...doc.querySelectorAll('.article-figure img,.article-inline-photo img,.article-body figure img')].map(el=>el.getAttribute('src')).filter(Boolean);
      const unique=[...new Set(urls.map(u=>new URL(u,location.origin).href))].filter(u=>{try{return ['ep1.pinkbike.org','descenso.cl'].includes(new URL(u).hostname)}catch{return false}}).slice(0,16);
      if(unique.length)render(unique);else if(!fallback.length)$('generator-status').textContent='Esta noticia no contiene fotografías compatibles.';
    }catch(error){if(!fallback.length)$('generator-status').textContent='No se pudieron cargar las fotografías: '+error.message}
  }
  async function fetchSource(url){
    const res=await fetch('/api/instagram-source?url='+encodeURIComponent(url),{headers:{authorization:'Bearer '+token}});
    if(!res.ok){const d=await res.json().catch(()=>({}));throw Error(d.error||'No se pudo cargar una foto');}
    const blob=await res.blob(),bitmap=await createImageBitmap(blob);return bitmap;
  }
  function drawCover(images,title,variant){
    const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1350;
    const ctx=canvas.getContext('2d');ctx.fillStyle='#09090b';ctx.fillRect(0,0,1080,1350);
    const draw=(img,x,y,w,h)=>{
      const s=Math.max(w/img.width,h/img.height),sw=w/s,sh=h/s;
      ctx.drawImage(img,(img.width-sw)/2,(img.height-sh)/2,sw,sh,x,y,w,h);
    };
    if(variant===0||images.length===1){draw(images[0],0,0,1080,1080)}
    else if(variant===1||images.length===2){draw(images[0],0,0,535,1080);draw(images[1],545,0,535,1080)}
    else{draw(images[0],0,0,1080,655);draw(images[1],0,665,535,415);draw(images[2],545,665,535,415)}
    ctx.fillStyle='#111114';ctx.fillRect(0,1080,1080,270);
    ctx.fillStyle='#d92d3b';ctx.fillRect(45,1110,76,7);
    ctx.fillStyle='#f7f7f7';ctx.font='bold 28px Arial,sans-serif';ctx.fillText('DESCENSO.CL  /  MOUNTAIN BIKE',45,1162);
    ctx.font='bold 48px Arial,sans-serif';
    const words=String(title).replace(/^VIDEO:\s*/i,'').split(/\s+/),lines=[];let line='';
    for(const word of words){const test=(line?line+' ':'')+word;if(ctx.measureText(test).width>975&&line){lines.push(line);line=word}else line=test}
    if(line)lines.push(line);
    const chosen=lines.slice(0,2);if(lines.length>2)chosen[1]=chosen[1].replace(/[.,;:!?]+$/,'')+'…';
    chosen.forEach((t,i)=>ctx.fillText(t,45,1220+i*55));
    return canvas;
  }
  async function generateCover(rotate=false){
    if(!selected||busy)return;
    const chosen=sourcePhotos.filter(p=>p.selected).slice(0,3);
    if(!chosen.length){$('generator-status').textContent='Marca las fotografías que quieras usar de la galería de arriba.';return;}
    if(!$('image-rights').checked){$('generator-status').textContent='Confirma primero que tienes derechos para usar las fotografías seleccionadas.';return;}
    busy=true;setButtons();$('generator-status').textContent='Creando portada editorial…';
    const id=slug(selected);
    const images=[];
    try{
      for(const p of chosen)images.push(await fetchSource(p.url));
      if(!selected||slug(selected)!==id)throw Error('Cambiaste de noticia durante la generación.');
      if(rotate)layoutIndex++;else layoutIndex=chosen.length===1?0:chosen.length===2?1:2;
      const variant=chosen.length===1?0:layoutIndex%3;
      const canvas=drawCover(images,selected.title,variant);
      let quality=.85,blob;
      do{blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',quality));quality-=.1}while(blob&&blob.size>450000&&quality>=.35);
      if(!blob||blob.size>500000)throw Error('La portada supera el tamaño permitido.');
      const jpeg=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob)});
      const res=await fetch('/api/instagram-image',{method:'POST',headers:{authorization:'Bearer '+token,'content-type':'application/json'},body:JSON.stringify({slug:id,jpeg})});
      const data=await res.json();if(!res.ok)throw Error(data.error||'No se pudo guardar');
      $('image-url').value=data.url;updatePreview();$('article-image').src=data.url+'&v='+Date.now();
      $('generator-status').textContent='Portada creada y guardada en el servidor. Presiona GUARDAR CAMBIOS para asociarla al borrador.';
      state('Portada generada. Nada se publicó en Instagram.');
    }catch(error){$('generator-status').textContent=error.message||'Error al generar la portada'}
    finally{images.forEach(img=>img.close());busy=false;setButtons()}
  }
  $('generate-cover').addEventListener('click',()=>generateCover(false));
  $('regenerate-cover').addEventListener('click',()=>generateCover(true));

  $('image-upload').addEventListener('change',async()=>{
    const file=$('image-upload').files?.[0];if(!file||!selected)return;
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)){state('Usa JPG, PNG o WebP.');return;}
    if(file.size>15*1024*1024){state('La imagen original no puede superar 15 MB.');return;}
    busy=true;setButtons();$('upload-status').textContent='Optimizando y subiendo portada…';
    try{
      const bitmap=await createImageBitmap(file),scale=Math.min(1,1600/Math.max(bitmap.width,bitmap.height));
      const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
      canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
      let quality=.85,blob;
      do{blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',quality));quality-=.1}while(blob&&blob.size>450000&&quality>=.35);
      if(!blob||blob.size>500000)throw Error('No se pudo reducir la foto. Prueba una imagen más pequeña.');
      const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob)});
      const res=await fetch('/api/instagram-image',{method:'POST',headers:{authorization:'Bearer '+token,'content-type':'application/json'},body:JSON.stringify({slug:slug(selected),jpeg:encoded})});
      const data=await res.json();if(!res.ok)throw Error(data.error||'No se pudo subir la portada');
      $('image-url').value=data.url;updatePreview();$('image-rights').checked=false;
      $('upload-status').textContent='Portada subida. Confirma los derechos y guarda los cambios.';
      state('Imagen lista. Todavía no se ha publicado.');
    }catch(error){$('upload-status').textContent=error.message||'Error al subir la imagen';}
    finally{busy=false;setButtons();}
  });
  $('open-cover').addEventListener('click',()=>{const src=$('article-image').src;if(!src)return;$('cover-large').src=src;$('cover-dialog').showModal();});
  $('close-cover').addEventListener('click',()=>$('cover-dialog').close());
  $('cover-dialog').addEventListener('click',e=>{if(e.target===$('cover-dialog'))$('cover-dialog').close()});
  $('caption').addEventListener('input',updatePreview);
  $('image-url').addEventListener('input',updatePreview);
  $('save').addEventListener('click',async()=>{busy=true;setButtons();try{await save()}catch(e){state(e.message)}finally{busy=false;setButtons()}});
  $('publish').addEventListener('click',async()=>{busy=true;setButtons();try{await beginPublish()}catch(e){uncertainPublish=true;state(e.message+' · Publicación detenida. Presiona ACTUALIZAR NOTICIAS para consultar el estado antes de cualquier nuevo intento.')}finally{busy=false;setButtons()}});
  $('test-meta').addEventListener('click',async()=>{
    const b=$('test-meta');b.disabled=true;info('Consultando la API de Meta sin publicar…');
    try{const verified=await (async()=>{const res=await fetch('/api/instagram?check=1',{headers:{authorization:'Bearer '+token},cache:'no-store'});const data=await res.json();if(!res.ok)throw Error(data.error||'Meta no respondió');return data})();
      $('connection-state').textContent='META RESPONDE · @'+verified.username+' · PERMISO DE PUBLICACIÓN AÚN SIN PROBAR';
      info('Identidad de Instagram verificada. No se publicó contenido.');
    }catch(error){
      const message=String(error.message||'Error desconocido');
      const tokenIssue=/190|access token|token de acceso|session|sesión|expir|revoc|invalidat|contraseña|password|oauth/i.test(message);
      const notice=tokenIssue?'Meta rechazó la autorización. Es probable que debas generar un token nuevo y actualizar INSTAGRAM_ACCESS_TOKEN en Cloudflare.':'No se pudo verificar Meta. Revisa el mensaje técnico de abajo.';
      $('connection-state').textContent=(tokenIssue?'META · AUTORIZACIÓN CADUCADA O REVOCADA':'META · CONEXIÓN NO VERIFICADA')+' — '+message.slice(0,180);
      info(notice+' Detalle: '+message);
    }finally{b.disabled=false;}
  });
  $('copy-caption').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('caption').value);state('Texto copiado.')}catch{state('No se pudo copiar automáticamente.')}});
})();