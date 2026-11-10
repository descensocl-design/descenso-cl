'use strict';
document.addEventListener('click', async event => {
  const button=event.target.closest('[data-copy-article-url]');
  if(!button) return;
  const url=button.dataset.copyArticleUrl;
  const scope=button.closest('.article-share');
  const notice=scope?.querySelector('.article-share-feedback');
  try{
    if(navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(url);
    } else {
      const temp=document.createElement('textarea');
      temp.value=url;temp.style.position='fixed';temp.style.opacity='0';
      document.body.append(temp);temp.select();
      if(!document.execCommand('copy')) throw new Error('Copia no disponible');
      temp.remove();
    }
    if(notice)notice.textContent='ENLACE COPIADO';
  }catch(err){
    if(notice)notice.textContent='COPIA EL ENLACE DESDE LA BARRA DEL NAVEGADOR';
  }
});
