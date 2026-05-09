-- Создаём расширения для Odoo
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Предоставляем права
GRANT ALL PRIVILEGES ON DATABASE odoo_db TO odoo;
GRANT ALL ON SCHEMA public TO odoo;
ALTER SCHEMA public OWNER TO odoo;