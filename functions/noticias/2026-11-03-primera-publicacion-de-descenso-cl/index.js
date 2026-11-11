// Noticia de prueba retirada definitivamente del catálogo editorial.
// HTTP 410 informa a buscadores de que la URL ya no está disponible.
export function onRequestGet() {
  return new Response('Esta publicación de prueba fue retirada de Descenso.cl.', {
    status: 410,
    headers: {
      'content-type': 'text/plain; charset=utf-8',
      'cache-control': 'no-store',
      'x-robots-tag': 'noindex, nofollow',
      'x-content-type-options': 'nosniff'
    }
  });
}
