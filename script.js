const state={posts:[],filter:'Todos',query:''};
const $=s=>document.querySelector(s);
function safeUrl(value,kind){try{const u=new URL(value);if(u.protocol!=='https:')return '';if(kind==='image')return u.href;if(kind==='video'){const host=u.hostname.toLowerCase();if(host==='youtu.be')return /^[\w-]{11}$/.test(u.pathname.slice(1))?u.pathname.slice(1):'';if(['youtube.com','www.youtube.com','m.youtube.com'].includes(host)){const id=u.searchParams.get('v');return id&&/^[\w-]{11}$/.test(id)?id:''}}}catch{}return ''}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
function formatDate(d){const t=new Date(d+'T12:00:00');return Number.isNaN(t.valueOf())?'':t.toLocaleDateString('es-CL',{day:'numeric',month:'long',year:'numeric'})}
function render(){const filtered=state.posts.filter(p=>(state.filter==='Todos'||p.category===state.filter||(state.filter==='Videos'&&p.youtube))&&[p.title,p.excerpt,p.category].join(' ').toLocaleLowerCase().includes(state.query));$('#section-title').textContent=state.filter==='Todos'?'ÚLTIMAS PUBLICACIONES':state.filter.toUpperCase();$('#count').textContent=`${filtered.length} PUBLICACIONES`;$('#empty').hidden=filtered.length>0;const root=$('#posts');root.replaceChildren();for(const p of filtered){const b=el('button','post');b.type='button';const thumb=el('div','thumb');const image=safeUrl(p.image,'image');if(image){const img=el('img');img.src=image;img.alt=p.title;img.loading='lazy';thumb.append(img)}else thumb.append(el('div','placeholder','DESCENSO.'));thumb.append(el('span','type',p.youtube?'▶ VIDEO':p.category.toUpperCase()));b.append(thumb);const body=el('div','post-body');body.append(el('div','meta',`${p.category.toUpperCase()}  /  ${formatDate(p.date)}`),el('h3','',p.title),el('p','',p.excerpt),el('span','read','LEER HISTORIA  ↗'));b.append(body);b.addEventListener('click',()=>openArticle(p));root.append(b)}}
function openArticle(p){const body=$('#article-body');body.replaceChildren();body.append(el('div','article-tag',p.category.toUpperCase()),el('h2','article-title',p.title),el('div','article-date',formatDate(p.date)));const image=safeUrl(p.image,'image');if(image){const img=el('img','article-cover');img.src=image;img.alt=p.title;body.append(img)}const copy=el('div','article-copy');for(const paragraph of (p.body||[])){copy.append(el('p','',paragraph))}body.append(copy);const id=safeUrl(p.youtube,'video');if(id){const iframe=el('iframe','video-frame');iframe.src=`https://www.youtube-nocookie.com/embed/${id}`;iframe.title=`Video: ${p.title}`;iframe.allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';iframe.allowFullscreen=true;iframe.loading='lazy';body.append(iframe)}if(p.link){try{const url=new URL(p.link);if(url.protocol==='https:'){const a=el('a','read','VER ENLACE EXTERNO ↗');a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';body.append(a)}}catch{}}$('#article').showModal()}
$('#close').addEventListener('click',()=>$('#article').close());$('#article').addEventListener('click',e=>{if(e.target===$('#article'))$('#article').close()});document.querySelectorAll('[data-filter]').forEach(btn=>btn.addEventListener('click',()=>{state.filter=btn.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===btn));render()}));$('#search').addEventListener('input',e=>{state.query=e.target.value.trim().toLocaleLowerCase();render()});fetch('data/posts.json').then(r=>{if(!r.ok)throw Error('No se pudo cargar publicaciones');return r.json()}).then(data=>{state.posts=Array.isArray(data)?data.filter(p=>p&&typeof p.title==='string'&&typeof p.category==='string').sort((a,b)=>b.date.localeCompare(a.date)):[];render()}).catch(()=>{$('#empty').hidden=false;$('#empty').textContent='No se pudieron cargar las publicaciones. Comprueba data/posts.json.'});

/* DESCENSO.CL — PORTADA EDITORIAL V2 */

function createPostCard(p) {
  const b = el('button', 'post');
  b.type = 'button';

  const thumb = el('div', 'thumb');
  const image = safeUrl(p.image, 'image');

  if (image) {
    const img = el('img');
    img.src = image;
    img.alt = p.title;
    img.loading = 'lazy';
    thumb.append(img);
  } else {
    thumb.append(el('div', 'placeholder', 'DESCENSO.'));
  }

  thumb.append(
    el('span', 'type', p.youtube ? '▶ VIDEO' : p.category.toUpperCase())
  );

  const body = el('div', 'post-body');
  body.append(
    el('div', 'meta', `${p.category.toUpperCase()} / ${formatDate(p.date)}`),
    el('h3', '', p.title),
    el('p', '', p.excerpt || ''),
    el('span', 'read', 'LEER HISTORIA ↗')
  );

  b.append(thumb, body);
  b.addEventListener('click', () => openArticle(p));
  return b;
}

function renderEditorial() {
  const filtered = state.posts.filter(p =>
    (state.filter === 'Todos' ||
      p.category === state.filter ||
      (state.filter === 'Videos' && p.youtube)) &&
    [p.title, p.excerpt, p.category]
      .join(' ')
      .toLocaleLowerCase()
      .includes(state.query)
  );

  const featured = document.querySelector('#featured');
  const root = document.querySelector('#posts');

  featured.replaceChildren();
  root.replaceChildren();

  const lead = filtered[0];

  if (lead) {
    featured.append(createPostCard(lead));
  }

  filtered.slice(1).forEach(p => {
    root.append(createPostCard(p));
  });

  featured.hidden = !lead;

  $('#section-title').textContent =
    state.filter === 'Todos'
      ? 'ÚLTIMAS NOTICIAS'
      : state.filter.toUpperCase();

  $('#count').textContent = `${filtered.length} PUBLICACIONES`;
  $('#empty').hidden = filtered.length > 0;

  const videoBox = document.querySelector('#latest-video');

  if (videoBox) {
    videoBox.replaceChildren();

    const video = state.posts.find(p =>
      safeUrl(p.youtube, 'video')
    );

    if (video) {
      const id = safeUrl(video.youtube, 'video');
      const iframe = el('iframe');
      iframe.src = `https://www.youtube-nocookie.com/embed/${id}`;
      iframe.title = video.title;
      iframe.loading = 'lazy';
      iframe.allowFullscreen = true;
      iframe.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; web-share';

      videoBox.append(iframe);
      videoBox.append(el('p', '', video.title));
    } else {
      videoBox.append(el('p', '', 'Próximamente, nuevos videos de Descenso.cl.'));
    }
  }
}

/* Sustituye la presentación anterior sin alterar la carga de noticias */
render = renderEditorial;
