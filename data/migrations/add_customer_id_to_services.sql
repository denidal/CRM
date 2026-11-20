-- Add customer_id FK columns to legacy contract tables (run once on moowifi)

ALTER TABLE internet
  ADD COLUMN IF NOT EXISTS customer_id INT NULL,
  ADD INDEX IF NOT EXISTS idx_internet_customer (customer_id);

ALTER TABLE hotspot
  ADD COLUMN IF NOT EXISTS customer_id INT NULL,
  ADD INDEX IF NOT EXISTS idx_hotspot_customer (customer_id);

ALTER TABLE interfiber
  ADD COLUMN IF NOT EXISTS customer_id INT NULL,
  ADD INDEX IF NOT EXISTS idx_interfiber_customer (customer_id);

-- Prefer the Python backfill (idempotent, name + musteri_no + enrich):
--   python -m data.migrations.backfill_service_sales --dry-run
--   python -m data.migrations.backfill_service_sales
--
-- Manual SQL alternative (case-sensitive unless collation folds case):
-- UPDATE internet i
-- JOIN customers c ON c.otel_adi COLLATE utf8mb4_unicode_ci = i.otel_adi COLLATE utf8mb4_unicode_ci
-- SET i.customer_id = c.id
-- WHERE i.customer_id IS NULL;
--
-- UPDATE hotspot h
-- JOIN customers c ON c.otel_adi COLLATE utf8mb4_unicode_ci = h.musteri_adi COLLATE utf8mb4_unicode_ci
-- SET h.customer_id = c.id
-- WHERE h.customer_id IS NULL;
--
-- UPDATE interfiber f
-- JOIN customers c ON c.otel_adi COLLATE utf8mb4_unicode_ci = f.otel_adi COLLATE utf8mb4_unicode_ci
-- SET f.customer_id = c.id
-- WHERE f.customer_id IS NULL;
