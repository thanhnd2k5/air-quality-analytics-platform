-- Warehouse logical schemas inside POSTGRES_DB (air_quality_dw).
-- Runs only on first Postgres volume initialization (P2-10).

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dwh;
CREATE SCHEMA IF NOT EXISTS mart;

COMMENT ON SCHEMA staging IS 'Bridge tables from processed lake to dbt/DWH';
COMMENT ON SCHEMA dwh IS 'Dimensional warehouse models (dims/facts)';
COMMENT ON SCHEMA mart IS 'Analytical marts for dashboard and ML hand-off';
