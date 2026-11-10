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

-- Reportes: crear sin tocar los comentarios ya publicados.
CREATE TABLE IF NOT EXISTS comment_reports (
  id TEXT PRIMARY KEY,
  comment_id TEXT NOT NULL,
  article_slug TEXT NOT NULL,
  reporter_hash TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(comment_id, reporter_hash)
);
CREATE INDEX IF NOT EXISTS idx_comments_report_lookup ON comment_reports(comment_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_visitor_article ON comments(visitor_hash,article_slug,created_at DESC);
-- Ver denuncias acumuladas antes de moderar:
-- SELECT comment_id, COUNT(*) AS reports FROM comment_reports GROUP BY comment_id ORDER BY reports DESC;
-- Ocultar comentario sin borrarlo:
-- UPDATE comments SET status='rejected' WHERE id='ID_DEL_COMENTARIO';
