-- Ejecutar en Cloudflare D1 antes de activar la sección de comentarios.
CREATE TABLE IF NOT EXISTS comments (
  id TEXT PRIMARY KEY,
  article_slug TEXT NOT NULL,
  display_name TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
  visitor_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_article_status ON comments(article_slug, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_visitor_time ON comments(visitor_hash, created_at DESC);
-- Para aprobar desde la consola D1:
-- UPDATE comments SET status='approved' WHERE id='ID_DEL_COMENTARIO';
-- Para ocultar:
-- UPDATE comments SET status='rejected' WHERE id='ID_DEL_COMENTARIO';
