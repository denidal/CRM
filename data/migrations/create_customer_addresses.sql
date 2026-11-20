"""Create customer_addresses for multi-site customers (Customer → N addresses)."""

-- PostgreSQL / MySQL compatible-ish; run via ORM INIT_SCHEMA or manually.

CREATE TABLE IF NOT EXISTS customer_addresses (
  id SERIAL PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  label VARCHAR(100) NULL,
  otel_adres TEXT NULL,
  il VARCHAR(100) NULL,
  ilce VARCHAR(100) NULL,
  mahalle VARCHAR(150) NULL,
  sokak_cadde VARCHAR(150) NULL,
  dis_kapi_no VARCHAR(50) NULL,
  ic_kapi_no VARCHAR(50) NULL,
  adres_kodu VARCHAR(50) NULL,
  posta_kodu VARCHAR(20) NULL,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customer_addresses_customer_id ON customer_addresses(customer_id);
