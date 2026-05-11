-- Demo-mode Postgres cleanup
--
-- Deletes Batch rows (Prisma) whose sessionId is a demo session AND that
-- are older than 2 hours. The Invoice rows cascade-delete via the FK in
-- frontend/prisma/schema.prisma (onDelete: Cascade).
--
-- The FastAPI APScheduler handles the matching SQLite + filesystem cleanup
-- every 15 min; this snippet is the Postgres half and is intended to be
-- run by cron, pg_cron, or Supabase's scheduled functions UI.
--
-- Cron example (every 15 min):
--   */15 * * * *  psql "$DATABASE_URL" -f /path/to/scripts/cleanup_demo.sql
--
-- pg_cron example:
--   SELECT cron.schedule('demo-cleanup', '*/15 * * * *',
--     $$DELETE FROM "Batch"
--        WHERE "sessionId" LIKE 'demo_%'
--          AND "createdAt" < NOW() - INTERVAL '2 hours'$$);

DELETE FROM "Batch"
WHERE "sessionId" LIKE 'demo_%'
  AND "createdAt" < NOW() - INTERVAL '2 hours';
