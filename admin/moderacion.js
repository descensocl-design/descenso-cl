'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const access=$('access-form'),input=$('moderation-token'),area=$('moderation-content');
  const view=$('moderation-view'),items=$('moderation-items'),status=$('moderation-status');
  let token='';
  function say(message){status.textContent=message;}
  const make=(tag,className,text)=>{
    const node=document.createElement(tag);
    if(className)node.className=className;
    if(text!==undefined)node.textContent=String(text);
    return node;
  };
  async function api(path,init={}){
    const response=await fetch('/api/moderation'+path,{
      ...init,cache:'no-store',headers:{...(init.headers||{}),authorization:'Bearer '+token}
    });
    let data;try{data=await response.json()}catch{throw new Error('El servidor no entregó JSON válido');}
    if(!response.ok)throw new Error(data.error||'No se pudo completar la solicitud');
    return data;
  }
  function render(comments){
    items.replaceChildren();
    if(!comments.length){items.append(make('p','moderation-empty','No hay comentarios en esta categoría.'));return;}
    for(const comment of comments){
      const card=make('article','moderation-card');
      const head=make('div','moderation-card-header');
      const date=new Date(comment.created_at);
      head.append(make('strong','',comment.display_name||'Anónimo'),
        make('span','',Number.isNaN(date.valueOf())?'':date.toLocaleString('es-CL')));
      card.append(head,make('p','moderation-comment',comment.message||''));
      const meta=make('div','moderation-meta');
      const a=make('a','',comment.article_slug||'Ver noticia');
      a.href='/noticias/'+encodeURIComponent(comment.article_slug)+'/';
      a.target='_blank';a.rel='noopener noreferrer';meta.append(a);
      meta.append(make('span','',String(comment.reports||0)+' reportes'));
      card.append(meta);
      const actions=make('div','moderation-actions');
      const button=make('button','',comment.status==='rejected'?'RESTAURAR':'OCULTAR');
      button.type='button';
      button.addEventListener('click',async()=>{
        const action=comment.status==='rejected'?'restore':'hide';
        if(!confirm((action==='hide'?'¿Ocultar':'¿Restaurar')+' este comentario?'))return;
        button.disabled=true;
        try{
          await api('',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:comment.id,action})});
          say('Cambio guardado.');await load();
        }catch(error){say(error.message);button.disabled=false;}
      });
      actions.append(button);card.append(actions);items.append(card);
    }
  }
  async function load(){
    say('Cargando comentarios...');
    try{const data=await api('?view='+encodeURIComponent(view.value));render(data.comments||[]);say((data.comments||[]).length+' comentarios cargados.');}
    catch(error){items.replaceChildren();say(error.message);}
  }
  access.addEventListener('submit',async event=>{
    event.preventDefault();
    token=input.value.trim();if(!token)return;
    input.value='';
    try{
      const data=await api('?view=reported');
      access.hidden=true;area.hidden=false;render(data.comments||[]);say('Acceso autorizado.');
    }catch(error){token='';say(error.message);}
  });
  view.addEventListener('change',load);
  $('moderation-refresh').addEventListener('click',load);
  $('moderation-logout').addEventListener('click',()=>{token='';items.replaceChildren();area.hidden=true;access.hidden=false;say('Sesión cerrada.');});
})();
