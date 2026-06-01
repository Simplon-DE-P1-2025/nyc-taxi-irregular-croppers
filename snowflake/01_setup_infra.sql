-- ============================================================================
--  01_setup_infra.sql — Setup de l'infrastructure Snowflake (BASE de départ)
--  Projet NYC Taxi. À exécuter sur CHAQUE compte (mode 1 compte/personne) :
--
--    snow sql -c projet7 -f snowflake/01_setup_infra.sql
--
--  Idempotent (CREATE ... IF NOT EXISTS). Crée l'ossature imposée par le brief.
--  ⚠️ La table RAW est laissée à COMPLÉTER après l'exploration des données (voir §4).
-- ============================================================================

USE ROLE ACCOUNTADMIN;

-- 1) Resource monitor : protège le quota du trial ($400). Notifie puis suspend.
CREATE RESOURCE MONITOR IF NOT EXISTS nyc_taxi_monitor
  WITH CREDIT_QUOTA = 100
       FREQUENCY = MONTHLY
       START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 50  PERCENT DO NOTIFY
    ON 80  PERCENT DO NOTIFY
    ON 95  PERCENT DO SUSPEND
    ON 100 PERCENT DO SUSPEND_IMMEDIATE;

-- 2) Warehouse (XSMALL pour économiser ; on pourra passer en MEDIUM pour les gros COPY).
CREATE WAREHOUSE IF NOT EXISTS NYC_TAXI_WH
  WITH WAREHOUSE_SIZE = 'XSMALL'
       AUTO_SUSPEND = 60
       AUTO_RESUME = TRUE
       INITIALLY_SUSPENDED = TRUE;

ALTER WAREHOUSE NYC_TAXI_WH SET RESOURCE_MONITOR = nyc_taxi_monitor;

-- 3) Base + schémas (architecture imposée RAW → STAGING → FINAL).
CREATE DATABASE IF NOT EXISTS NYC_TAXI_DB;
CREATE SCHEMA IF NOT EXISTS NYC_TAXI_DB.RAW;
CREATE SCHEMA IF NOT EXISTS NYC_TAXI_DB.STAGING;
CREATE SCHEMA IF NOT EXISTS NYC_TAXI_DB.FINAL;

USE WAREHOUSE NYC_TAXI_WH;
USE DATABASE  NYC_TAXI_DB;
USE SCHEMA    RAW;

-- 4) TABLE RAW — À COMPLÉTER après l'exploration des données (brique EDA, sprint J1).
--    Méthode :
--      • Inspecter le schéma RÉEL d'un fichier Parquet (colonnes + types) — NE PAS recopier
--        aveuglément le DDL du brief, le vérifier sur la donnée.
--      • Vérifier la stabilité du schéma entre 2024 et 2025 (colonnes qui apparaissent/disparaissent).
--      • Prévoir des colonnes nullable + d'éventuelles métadonnées de chargement (source_file, loaded_at).
--
-- CREATE TABLE IF NOT EXISTS RAW.yellow_taxi_trips (
--     ...   -- <— à définir par l'équipe d'après l'EDA
-- );

-- 5) Stage interne pour recevoir les Parquet (PUT depuis l'ingestion).
--    NB : le chargement direct depuis l'URL CloudFront ne fonctionne pas (ce n'est pas un bucket S3).
CREATE STAGE IF NOT EXISTS RAW.nyc_taxi_stage
  FILE_FORMAT = (TYPE = PARQUET);

-- 6) Contrôles.
SHOW WAREHOUSES LIKE 'NYC_TAXI_WH';
SHOW SCHEMAS IN DATABASE NYC_TAXI_DB;

-- ── Suite : définir la table RAW (après EDA) → ingestion (PUT + COPY INTO) → dbt.
