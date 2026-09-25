-- Create Airflow metadata database on first Postgres init (P2-10).
-- Uses psql \gexec (supported by official postgres image entrypoint).

SELECT 'CREATE DATABASE airflow_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow_db')\gexec
