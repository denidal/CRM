-- Unified service sales under customer (Customer → N ServiceSale)
-- POP/RADIUS optional on the service row.

CREATE TABLE IF NOT EXISTS service_sales (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  service_type VARCHAR(30) NOT NULL COMMENT 'internet|hotspot|interfiber',
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  pop_id INT NULL,
  radius_username VARCHAR(100) NULL,
  hat_no VARCHAR(50) NULL,
  paket_adi VARCHAR(255) NULL,
  internet_hiz VARCHAR(50) NULL,
  fiyat DECIMAL(15,2) NULL,
  para_birimi VARCHAR(10) NULL DEFAULT 'TL',
  sozlesme_no VARCHAR(100) NULL,
  sozlesme_suresi VARCHAR(50) NULL,
  sozlesme_baslangic_tarihi DATE NULL,
  sozlesme_bitis_tarihi DATE NULL,
  orijinal_sozlesme_no VARCHAR(100) NULL,
  hizmet_tipi VARCHAR(10) NULL,
  abone_baslangic DATE NULL,
  abone_bitis DATE NULL,
  contract_durum VARCHAR(50) NULL DEFAULT 'onaylandı',
  notes TEXT NULL,
  legacy_table VARCHAR(30) NULL,
  legacy_id INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_ss_customer (customer_id),
  INDEX idx_ss_pop (pop_id),
  INDEX idx_ss_hat (hat_no),
  INDEX idx_ss_type (service_type),
  UNIQUE KEY uq_ss_legacy (legacy_table, legacy_id),
  CONSTRAINT fk_ss_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
  CONSTRAINT fk_ss_pop FOREIGN KEY (pop_id) REFERENCES pops(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Backfill: python -m data.migrations.backfill_service_sales --dry-run
--           python -m data.migrations.backfill_service_sales

-- Backfill helpers: add customer_id to legacy contract tables if missing
-- ALTER TABLE internet ADD COLUMN customer_id INT NULL, ADD INDEX idx_internet_customer (customer_id);
-- ALTER TABLE hotspot ADD COLUMN customer_id INT NULL, ADD INDEX idx_hotspot_customer (customer_id);
-- ALTER TABLE interfiber ADD COLUMN customer_id INT NULL, ADD INDEX idx_interfiber_customer (customer_id);

-- Optional: link BTK abone rows to service_sales
-- ALTER TABLE btk_abone_rehber ADD COLUMN service_sale_id INT NULL, ADD INDEX idx_btk_ss (service_sale_id);
