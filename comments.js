'use strict';
// El formulario no se activa hasta que la API confirme que existe almacenamiento.
(async function(){
  const root = document.getElementById('comments');
  if(!root) return;
  const slug = root.dataset.article;
  const list = root.querySelector('[data-comments-list]');
  const status = root.querySelector('[data-comments-status]');
  const form = root.querySelector('form');
  const nameInput = form.elements.namedItem('name');
  const anonymous = form.elements.namedItem('anonymous');
  const message = form.elements.namedItem('message');
  const send = form.querySelector('button[type=submit]');
  const honeypot = form.elements.namedItem('website');
  const endpoint = '/api/comments/' + encodeURIComponent(slug);
  const reportEndpoint = '/api/comment-reports/' + encodeURIComponent(slug);
  function reportButton(comment){
    const button=document.createElement('button');
    button.type='button';button.className='comment-report-button';
    button.textContent='REPORTAR';
    button.dataset.commentId=comment.id;
    button.setAttribute('aria-label','Reportar comentario de '+comment.display_name);
    return button;
  }
  list.addEventListener('click',async event=>{
    const button=event.target.closest('.comment-report-button');
    if(!button||button.disabled)return;
    const reason=window.prompt('¿Por qué quieres reportar este comentario? Escribe: spam, abuso u otro','abuso');
    if(reason===null)return;
    const selected=reason.trim().toLocaleLowerCase();
    if(!['spam','abuso','otro'].includes(selected)){
      status.textContent='Usa una de estas opciones: spam, abuso u otro.';
      return;
    }
    button.disabled=true;
    try{
      const response=await fetch(reportEndpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({comment_id:button.dataset.commentId,reason:selected})});
      const data=await response.json();
      status.textContent=data.message||data.error||'No se pudo enviar el reporte';
      if(response.ok)button.textContent='REPORTADO';
      else button.disabled=false;
    }catch{
      status.textContent='No se pudo enviar el reporte';button.disabled=false;
    }
  });

  anonymous.addEventListener('change',()=>{nameInput.disabled=anonymous.checked;nameInput.required=!anonymous.checked});
  try {
    const res=await fetch(endpoint,{cache:'no-store'});
    const data=await res.json();
    if(!res.ok||!data.configured){
      status.textContent='Los comentarios estarán disponibles próximamente.';
      form.hidden=true; return;
    }
    status.textContent='Comparte tu opinión. Tu comentario se publica al instante.';
    list.replaceChildren();
    const countNode = root.querySelector('[data-comment-count]');
    if(countNode)countNode.textContent=String(data.comments.length);
    if(!data.comments.length){
      const empty=document.createElement('p');empty.textContent='Todavía no hay comentarios. Sé el primero.';list.append(empty);
    }
    for(const comment of data.comments){
      const article=document.createElement('article');article.className='reader-comment';
      const header=document.createElement('div');header.className='reader-comment-head';
      const author=document.createElement('strong');author.textContent=comment.display_name;
      const date=document.createElement('time');date.textContent=new Date(comment.created_at).toLocaleDateString('es-CL');
      const body=document.createElement('p');body.textContent=comment.message;
      header.append(author,date);article.append(header,body,reportButton(comment));list.append(article);
    }
    form.hidden=false;
  } catch(e){status.textContent='Los comentarios no están disponibles en este momento.';form.hidden=true}
  form.addEventListener('submit',async e=>{
    e.preventDefault();send.disabled=true;status.textContent='Enviando comentario…';
    try{
      const res=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:nameInput.value,anonymous:anonymous.checked,message:message.value,website:honeypot?.value||''})});
      const data=await res.json();
      status.textContent=data.message||data.error||'No se pudo enviar';
      if(res.ok && data.comment) {
        const previouslyEmpty=list.querySelector('p');
        if(previouslyEmpty && previouslyEmpty.textContent.includes('Todavía no hay comentarios'))previouslyEmpty.remove();
        const article=document.createElement('article');
        article.className='reader-comment';
        const header=document.createElement('div');
        header.className='reader-comment-head';
        const author=document.createElement('strong');
        author.textContent=data.comment.display_name;
        const date=document.createElement('time');
        date.textContent=new Date(data.comment.created_at).toLocaleDateString('es-CL');
        const body=document.createElement('p');
        body.textContent=data.comment.message;
        header.append(author,date);
        article.append(header,body,reportButton(data.comment));
        list.prepend(article);
        const countNode=root.querySelector('[data-comment-count]');
        if(countNode)countNode.textContent=String((Number(countNode.textContent)||0)+1);
        form.reset();
        nameInput.disabled=false;
        nameInput.required=true;
      }
    } catch(e){status.textContent='No se pudo conectar con el servidor.'}
    finally{send.disabled=false}
  });
})();


// Diseño editorial: distribuir fotografías entre párrafos y mostrar videos embebibles.
(async function enhanceArticleMedia(){
  const copy=document.querySelector('.article-page .article-copy');
  if(!copy) return;
  const gallery=document.querySelector('.article-page .article-gallery');
  if(gallery){
    const figures=[...gallery.querySelectorAll('figure')];
    const paragraphs=[...copy.querySelectorAll(':scope > p')];
    // Mantener el titular y la portada; intercalar imágenes adicionales después de párrafos.
    if(figures.length && paragraphs.length){
      const spacing=Math.max(1,Math.floor(paragraphs.length/(figures.length+1)));
      figures.forEach((fig,i)=>{
        fig.classList.add('article-inline-photo');
        const target=paragraphs[Math.min(paragraphs.length-1,(i+1)*spacing-1)];
        target.after(fig);
      });
      if(!gallery.querySelector('figure'))gallery.remove();
    }
  }
  // El generador del servidor ya inserta el reproductor original.
  // No añadirlo nuevamente desde el navegador cuando existe uno.
  if (copy.querySelector('.article-video iframe')) return;
  // Los videos deben contener una URL real de YouTube/Vimeo; nunca simular reproductores.
  try{
    const res=await fetch('/data/posts.json',{cache:'no-store'});
    if(!res.ok)return;
    const posts=await res.json();
    const path=location.pathname.replace(/\/?$/,'/');
    const post=posts.find(p=>p.permalink===path);
    if(!post)return;
    const urls=[post.youtube,post.video,post.video_url,...(Array.isArray(post.videos)?post.videos:[])].filter(Boolean);
    const seen=new Set();
    let first=true;
    for(const raw of urls){
      let u;try{u=new URL(raw)}catch{continue}
      let embed='';
      if(['youtube.com','www.youtube.com','m.youtube.com'].includes(u.hostname)){
        const id=u.searchParams.get('v')||u.pathname.match(/^\/(?:shorts|embed|live)\/([A-Za-z0-9_-]{11})/)?.[1];
        if(id&&/^[A-Za-z0-9_-]{11}$/.test(id))embed='https://www.youtube-nocookie.com/embed/'+id;
      }else if(u.hostname==='youtu.be'){
        const id=u.pathname.slice(1);if(/^[A-Za-z0-9_-]{11}$/.test(id))embed='https://www.youtube-nocookie.com/embed/'+id;
      }else if(['vimeo.com','www.vimeo.com','player.vimeo.com'].includes(u.hostname)){
        const id=u.pathname.match(/\/(?:video\/)?(\d+)/)?.[1];if(id)embed='https://player.vimeo.com/video/'+id;
      }
      if(!embed||seen.has(embed))continue;
      seen.add(embed);
      const figure=document.createElement('figure');
      figure.className='article-video';
      const frame=document.createElement('iframe');
      frame.src=embed;frame.title='Video de la noticia';frame.loading='lazy';
      frame.allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
      frame.allowFullscreen=true;frame.referrerPolicy='strict-origin-when-cross-origin';
      figure.append(frame);
      const pp=[...copy.querySelectorAll(':scope > p')];
      const anchor=pp[Math.min(pp.length-1,first?1:Math.floor(pp.length/2))];
      if(anchor)anchor.after(figure);else copy.append(figure);
      first=false;
    }
  }catch(e){/* Sin datos de video: conservar el artículo existente. */}
})();
