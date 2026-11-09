
'use strict';

// DESCENSO.CL — PORTADA DE NOTICIAS

const state = {
  posts: [],
  filter: 'Todos',
  query: ''
};

const $ = selector => document.querySelector(selector);

function el(tag, className = '', text) {
  const element = document.createElement(tag);

  if (className) {
    element.className = className;
  }

  if (text !== undefined) {
    element.textContent = String(text);
  }

  return element;
}

function safeUrl(value, kind) {
  try {
    const url = new URL(value);

    if (url.protocol !== 'https:') {
      return '';
    }

    if (kind === 'image') {
      return url.href;
    }

    if (kind === 'video') {
      const host = url.hostname.toLowerCase();

      if (host === 'youtu.be') {
        const id = url.pathname.slice(1);
        return /^[\w-]{11}$/.test(id) ? id : '';
      }

      if (
        ['youtube.com', 'www.youtube.com', 'm.youtube.com']
          .includes(host)
      ) {
        const id = url.searchParams.get('v');
        return id && /^[\w-]{11}$/.test(id) ? id : '';
      }
    }
  } catch (error) {
    return '';
  }

  return '';
}

function formatDate(value) {
  const date = new Date(String(value || '') + 'T12:00:00');

  if (Number.isNaN(date.valueOf())) {
    return '';
  }

  return date.toLocaleDateString('es-CL', {
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  });
}

function articleUrl(post) {
  if (/^\/noticias\/[a-z0-9-]+\/$/.test(post.permalink || '')) return post.permalink;
  const title = String(post.title || 'noticia');
  const slug = title.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 85);
  const date = /^\d{4}-\d{2}-\d{2}$/.test(post.date) ? post.date : 'sin-fecha';
  return `/noticias/${date}-${slug}/`;
}

function categoryCover(category) {
  const names = ['downhill', 'enduro', 'freeride', 'xc'];
  const key = String(category || '').toLowerCase();
  return `/assets/portadas/${names.includes(key) ? key : 'mundo'}.svg`;
}

function createPostCard(post) {
  const button = el('a', 'post');
  button.href = articleUrl(post);

  const thumb = el('div', 'thumb');
  const image = safeUrl(post.image, 'image') || categoryCover(post.category);

  if (image) {
    const img = el('img');
    img.src = image;
    img.alt = post.title;
    img.loading = 'lazy';
    thumb.append(img);
  } else {
    thumb.append(
      el('div', 'placeholder', 'DESCENSO.')
    );
  }

  thumb.append(
    el(
      'span',
      'type',
      post.youtube
        ? '▶ VIDEO'
        : String(post.category).toUpperCase()
    )
  );

  const body = el('div', 'post-body');

  body.append(
    el(
      'div',
      'meta',
      `${String(post.category).toUpperCase()} / ${formatDate(post.date)}`
    ),
    el('h3', '', post.title),
    el('p', '', post.excerpt || ''),
    el('span', 'read', 'LEER HISTORIA ↗')
  );

  button.append(thumb, body);


  return button;
}

function openArticle(post) {
  const dialog = $('#article');
  const body = $('#article-body');

  if (!dialog || !body) {
    return;
  }

  body.replaceChildren();

  body.append(
    el(
      'div',
      'article-tag',
      String(post.category).toUpperCase()
    ),
    el('h2', 'article-title', post.title),
    el('div', 'article-date', formatDate(post.date))
  );

  const image = safeUrl(post.image, 'image') || categoryCover(post.category);

  if (image) {
    const img = el('img', 'article-cover');
    img.src = image;
    img.alt = post.title;
    body.append(img);
  }

  const copy = el('div', 'article-copy');

  const paragraphs = Array.isArray(post.body)
    ? post.body
    : typeof post.body === 'string'
      ? [post.body]
      : [];

  for (const paragraph of paragraphs) {
    copy.append(
      el('p', '', String(paragraph))
    );
  }

  body.append(copy);

  const videoId = safeUrl(post.youtube, 'video');

  if (videoId) {
    const iframe = el('iframe', 'video-frame');

    iframe.src =
      `https://www.youtube-nocookie.com/embed/${videoId}`;

    iframe.title = `Video: ${post.title}`;
    iframe.loading = 'lazy';
    iframe.allowFullscreen = true;

    iframe.allow =
      'accelerometer; autoplay; encrypted-media; ' +
      'gyroscope; picture-in-picture; web-share';

    body.append(iframe);
  }

  if (post.link) {
    try {
      const url = new URL(post.link);

      if (url.protocol === 'https:') {
        const link = el(
          'a',
          'read',
          'VER FUENTE ORIGINAL ↗'
        );

        link.href = url.href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';

        body.append(link);
      }
    } catch (error) {
      console.warn('Enlace de fuente inválido');
    }
  }

  if (typeof dialog.showModal === 'function') {
    dialog.showModal();
  }
}

function render() {
  const filtered = state.posts.filter(post => {
    const matchesCategory =
      state.filter === 'Todos' ||
      post.category === state.filter ||
      (state.filter === 'Videos' && post.youtube);

    const searchableText = [
      post.title,
      post.excerpt,
      post.category
    ].join(' ').toLocaleLowerCase();

    return (
      matchesCategory &&
      searchableText.includes(state.query)
    );
  });

  const featured = $('#featured');
  const root = $('#posts');
  const empty = $('#empty');
  const count = $('#count');
  const sectionTitle = $('#section-title');

  if (!root) {
    console.error(
      'DESCENSO: no existe el contenedor #posts'
    );
    return;
  }

  root.replaceChildren();

  if (featured) {
    featured.replaceChildren();

    if (filtered.length > 0) {
      featured.append(
        createPostCard(filtered[0])
      );
    }

    featured.hidden = filtered.length === 0;

    for (const post of filtered.slice(1)) {
      root.append(createPostCard(post));
    }
  } else {
    // Si no existe #featured, muestra todas
    // las noticias directamente en #posts.
    for (const post of filtered) {
      root.append(createPostCard(post));
    }
  }

  if (sectionTitle) {
    sectionTitle.textContent =
      state.filter === 'Todos'
        ? 'ÚLTIMAS NOTICIAS'
        : state.filter.toUpperCase();
  }

  if (count) {
    count.textContent =
      `${filtered.length} PUBLICACIONES`;
  }

  if (empty) {
    empty.hidden = filtered.length > 0;
  }

  const videoBox = $('#latest-video');

  if (videoBox) {
    videoBox.replaceChildren();

    const video = state.posts.find(post =>
      safeUrl(post.youtube, 'video')
    );

    if (video) {
      const videoId = safeUrl(
        video.youtube,
        'video'
      );

      const iframe = el('iframe');

      iframe.src =
        `https://www.youtube-nocookie.com/embed/${videoId}`;

      iframe.title = video.title;
      iframe.loading = 'lazy';
      iframe.allowFullscreen = true;

      videoBox.append(
        iframe,
        el('p', '', video.title)
      );
    } else {
      videoBox.append(
        el(
          'p',
          '',
          'Próximamente, nuevos videos de Descenso.cl.'
        )
      );
    }
  }
}

function initialize() {
  const closeButton = $('#close');
  const dialog = $('#article');
  const search = $('#search');

  if (closeButton && dialog) {
    closeButton.addEventListener('click', () => {
      dialog.close();
    });
  }

  if (dialog) {
    dialog.addEventListener('click', event => {
      if (event.target === dialog) {
        dialog.close();
      }
    });
  }

  document
    .querySelectorAll('[data-filter]')
    .forEach(button => {
      button.addEventListener('click', () => {
        state.filter = button.dataset.filter;

        document
          .querySelectorAll('[data-filter]')
          .forEach(item => {
            item.classList.toggle(
              'active',
              item === button
            );
          });

        render();
      });
    });

  if (search) {
    search.addEventListener('input', event => {
      state.query = event.target.value
        .trim()
        .toLocaleLowerCase();

      render();
    });
  }

  loadPosts();
}

async function loadPosts() {
  try {
    const response = await fetch(
      '/data/posts.json',
      { cache: 'no-store' }
    );

    if (!response.ok) {
      throw new Error(
        `Error HTTP ${response.status}`
      );
    }

    const data = await response.json();

    if (!Array.isArray(data)) {
      throw new Error(
        'posts.json no contiene una lista'
      );
    }

    state.posts = data
      .filter(post =>
        post &&
        typeof post.title === 'string' &&
        typeof post.category === 'string'
      )
      .sort((a, b) =>
        String(b.date || '').localeCompare(
          String(a.date || '')
        )
      );

    console.log(
      'DESCENSO: noticias cargadas:',
      state.posts.length
    );

    render();

  } catch (error) {
    console.error(
      'DESCENSO: error al cargar noticias:',
      error
    );

    const empty = $('#empty');

    if (empty) {
      empty.hidden = false;
      empty.textContent =
        'No se pudieron cargar las noticias.';
    }
  }
}

if (document.readyState === 'loading') {
  document.addEventListener(
    'DOMContentLoaded',
    initialize
  );
} else {
  initialize();
}
