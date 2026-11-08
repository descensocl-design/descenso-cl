
'use strict';

const state = {posts: [], filter: 'Todos', query: ''};
const $ = selector => document.querySelector(selector);

function el(tag, cls = '', value) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (value !== undefined) node.textContent = value;
  return node;
}

function safeUrl(value, kind) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return '';
    if (kind === 'image') return url.href;
    if (kind === 'video') {
      const host = url.hostname.toLowerCase();
      if (host === 'youtu.be') return /^[\w-]{11}$/.test(url.pathname.slice(1)) ? url.pathname.slice(1) : '';
      if (['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(host)) {
        const id = url.searchParams.get('v');
        return id && /^[\w-]{11}$/.test(id) ? id : '';
      }
    }
  } catch (_) {}
  return '';
}

function formatDate(value) {
  const date = new Date(String(value || '') + 'T12:00:00');
  return Number.isNaN(date.valueOf()) ? '' : date.toLocaleDateString('es-CL', {day: 'numeric', month: 'long', year: 'numeric'});
}

function createPostCard(post) {
  const button = el('button', 'post');
  button.type = 'button';
  const thumb = el('div', 'thumb');
  const image = safeUrl(post.image, 'image');
  if (image) {
    const img = el('img');
    img.src = image;
    img.alt = post.title;
    img.loading = 'lazy';
    thumb.append(img);
  } else {
    thumb.append(el('div', 'placeholder', 'DESCENSO.'));
  }
  thumb.append(el('span', 'type', post.youtube ? '▶ VIDEO' : post.category.toUpperCase()));
  const body = el('div', 'post-body');
  body.append(
    el('div', 'meta', `${post.category.toUpperCase()} / ${formatDate(post.date)}`),
    el('h3', '', post.title),
    el('p', '', post.excerpt || ''),
    el('span', 'read', 'LEER HISTORIA ↗')
  );
  button.append(thumb, body);
  button.addEventListener('click', () => openArticle(post));
  return button;
}

function openArticle(post) {
  const body = $('#article-body');
  body.replaceChildren();
  body.append(
    el('div', 'article-tag', post.category.toUpperCase()),
    el('h2', 'article-title', post.title),
    el('div', 'article-date', formatDate(post.date))
  );
  const image = safeUrl(post.image, 'image');
  if (image) {
    const img = el('img', 'article-cover');
    img.src = image;
    img.alt = post.title;
    body.append(img);
  }
  const copy = el('div', 'article-copy');
  for (const paragraph of (Array.isArray(post.body) ? post.body : [])) {
    copy.append(el('p', '', String(paragraph)));
  }
  body.append(copy);
  const videoId = safeUrl(post.youtube, 'video');
  if (videoId) {
    const frame = el('iframe', 'video-frame');
    frame.src = `https://www.youtube-nocookie.com/embed/${videoId}`;
    frame.title = `Video: ${post.title}`;
    frame.loading = 'lazy';
    frame.allowFullscreen = true;
    frame.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; web-share';
    body.append(frame);
  }
  if (post.link) {
    try {
      const url = new URL(post.link);
      if (url.protocol === 'https:') {
        const link = el('a', 'read', 'VER FUENTE ORIGINAL ↗');
        link.href = url.href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        body.append(link);
      }
    } catch (_) {}
  }
  $('#article').showModal();
}

function render() {
  const filtered = state.posts.filter(post =>
    (state.filter === 'Todos' || post.category === state.filter || (state.filter === 'Videos' && post.youtube)) &&
    [post.title, post.excerpt, post.category].join(' ').toLocaleLowerCase().includes(state.query)
  );
  const featured = $('#featured');
  const root = $('#posts');
  featured.replaceChildren();
  root.replaceChildren();
  if (filtered.length) featured.append(createPostCard(filtered[0]));
  featured.hidden = filtered.length === 0;
  for (const post of filtered.slice(1)) root.append(createPostCard(post));
  $('#section-title').textContent = state.filter === 'Todos' ? 'ÚLTIMAS NOTICIAS' : state.filter.toUpperCase();
  $('#count').textContent = `${filtered.length} PUBLICACIONES`;
  $('#empty').hidden = filtered.length > 0;
  const videoBox = $('#latest-video');
  if (videoBox) {
    videoBox.replaceChildren();
    const video = state.posts.find(post => safeUrl(post.youtube, 'video'));
    if (video) {
      const frame = el('iframe');
      frame.src = `https://www.youtube-nocookie.com/embed/${safeUrl(video.youtube, 'video')}`;
      frame.title = video.title;
      frame.loading = 'lazy';
      frame.allowFullscreen = true;
      frame.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; web-share';
      videoBox.append(frame, el('p', '', video.title));
    } else {
      videoBox.append(el('p', '', 'Próximamente, nuevos videos de Descenso.cl.'));
    }
  }
}

$('#close').addEventListener('click', () => $('#article').close());
$('#article').addEventListener('click', event => {
  if (event.target === $('#article')) $('#article').close();
});

document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  state.filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(item => item.classList.toggle('active', item === button));
  render();
}));

$('#search').addEventListener('input', event => {
  state.query = event.target.value.trim().toLocaleLowerCase();
  render();
});

fetch('data/posts.json', {cache: 'no-store'})
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    state.posts = Array.isArray(data)
      ? data.filter(post => post && typeof post.title === 'string' && typeof post.category === 'string')
          .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')))
      : [];
    render();
  })
  .catch(error => {
    console.error('No se pudieron cargar las publicaciones:', error);
    $('#empty').hidden = false;
    $('#empty').textContent = 'No se pudieron cargar las publicaciones. Comprueba data/posts.json.';
  });
