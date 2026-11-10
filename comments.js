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
  const endpoint = '/api/comments/' + encodeURIComponent(slug);
  anonymous.addEventListener('change',()=>{nameInput.disabled=anonymous.checked;nameInput.required=!anonymous.checked});
  try {
    const res=await fetch(endpoint,{cache:'no-store'});
    const data=await res.json();
    if(!res.ok||!data.configured){
      status.textContent='Los comentarios estarán disponibles próximamente.';
      form.hidden=true; return;
    }
    status.textContent='Comparte tu opinión. Los comentarios se revisan antes de aparecer.';
    list.replaceChildren();
    if(!data.comments.length){
      const empty=document.createElement('p');empty.textContent='Todavía no hay comentarios. Sé el primero.';list.append(empty);
    }
    for(const comment of data.comments){
      const article=document.createElement('article');article.className='reader-comment';
      const header=document.createElement('div');header.className='reader-comment-head';
      const author=document.createElement('strong');author.textContent=comment.display_name;
      const date=document.createElement('time');date.textContent=new Date(comment.created_at).toLocaleDateString('es-CL');
      const body=document.createElement('p');body.textContent=comment.message;
      header.append(author,date);article.append(header,body);list.append(article);
    }
    form.hidden=false;
  } catch(e){status.textContent='Los comentarios no están disponibles en este momento.';form.hidden=true}
  form.addEventListener('submit',async e=>{
    e.preventDefault();send.disabled=true;status.textContent='Enviando comentario…';
    try{
      const res=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:nameInput.value,anonymous:anonymous.checked,message:message.value})});
      const data=await res.json();
      status.textContent=data.message||data.error||'No se pudo enviar';
      if(res.ok) form.reset();
    } catch(e){status.textContent='No se pudo conectar con el servidor.'}
    finally{send.disabled=false}
  });
})();
