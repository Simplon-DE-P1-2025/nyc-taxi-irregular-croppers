-- ============================================================================
--  02_monitoring.sql — Vues de supervision (thème « supervision & maintenance »)
--  Projet NYC Taxi. À exécuter après 01_setup_infra.sql :
--
--    snow sql -c projet7 -f snowflake/02_monitoring.sql
--
--  Idempotent (CREATE OR REPLACE VIEW). Crée un schéma MONITORING dédié :
--  RAW/STAGING/FINAL = couches DATA du pipeline ; la supervision est un concern
--  orthogonal (pattern standard : schéma ops séparé, cf. dbt-snowflake-monitoring).
--
--  Les vues s'exécutent avec les droits de leur propriétaire (ACCOUNTADMIN) →
--  elles ENCAPSULENT l'accès à SNOWFLAKE.ACCOUNT_USAGE : un consommateur (API,
--  dashboard) n'a besoin que d'un SELECT sur le schéma MONITORING.
--
--  ⚠️ Latence ACCOUNT_USAGE : ~45 min (QUERY_HISTORY) à ~3 h (METERING).
--     vw_pipeline_freshness lit les tables du projet → temps réel.
-- ============================================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE NYC_TAXI_WH;
USE DATABASE NYC_TAXI_DB;

CREATE SCHEMA IF NOT EXISTS MONITORING;
USE SCHEMA MONITORING;

-- ----------------------------------------------------------------------------
-- 1) Crédits compute par jour et par warehouse (30 derniers jours).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_credits_daily AS
SELECT
    date_trunc('day', start_time)::date           AS day,
    warehouse_name,
    round(sum(credits_used_compute), 4)           AS credits_compute,
    round(sum(credits_used_cloud_services), 4)    AS credits_cloud_services,
    round(sum(credits_used), 4)                   AS credits_total
FROM snowflake.account_usage.warehouse_metering_history
WHERE start_time > dateadd('day', -30, current_timestamp())
GROUP BY 1, 2;

-- ----------------------------------------------------------------------------
-- 2) Coût estimé du mois en cours (3 $/crédit ≈ édition Standard ; à ajuster).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_cost_month AS
SELECT
    date_trunc('month', current_date())::date     AS month,
    round(sum(credits_used), 2)                   AS credits,
    round(sum(credits_used) * 3.00, 2)            AS estimated_cost_usd
FROM snowflake.account_usage.warehouse_metering_history
WHERE start_time >= date_trunc('month', current_date());

-- ----------------------------------------------------------------------------
-- 3) Santé des requêtes (7 derniers jours) : volume, échecs, durées.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_queries_health AS
SELECT
    count(*)                                                                AS total_queries,
    count_if(execution_status = 'FAIL')                                     AS failed_queries,
    round(count_if(execution_status = 'FAIL') / nullif(count(*), 0) * 100, 2) AS fail_rate_pct,
    round(avg(total_elapsed_time) / 1000, 2)                                AS avg_duration_s,
    round(max(total_elapsed_time) / 1000, 2)                                AS max_duration_s
FROM snowflake.account_usage.query_history
WHERE start_time > dateadd('day', -7, current_timestamp());

-- ----------------------------------------------------------------------------
-- 4) Top 10 requêtes les plus longues (7 j). Tri sur la durée : meilleur proxy
--    du coût compute (les crédits warehouse ne sont pas attribués par requête ;
--    credits_used_cloud_services ne couvre que la couche cloud services).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_top_queries AS
SELECT
    query_id,
    left(query_text, 200)                         AS query_excerpt,
    user_name,
    warehouse_name,
    round(total_elapsed_time / 1000, 2)           AS duration_s,
    credits_used_cloud_services
FROM snowflake.account_usage.query_history
WHERE start_time > dateadd('day', -7, current_timestamp())
ORDER BY total_elapsed_time DESC
LIMIT 10;

-- ----------------------------------------------------------------------------
-- 5) Requêtes échouées récentes (7 j) — diagnostic.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_failed_queries AS
SELECT
    query_id,
    left(query_text, 200)                         AS query_excerpt,
    error_code,
    error_message,
    user_name,
    start_time
FROM snowflake.account_usage.query_history
WHERE execution_status = 'FAIL'
  AND start_time > dateadd('day', -7, current_timestamp());

-- ----------------------------------------------------------------------------
-- 6) Stockage (30 derniers jours) : données + stages + fail-safe, en GB.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_storage AS
SELECT
    usage_date,
    round(storage_bytes   / power(1024, 3), 3)    AS storage_gb,
    round(stage_bytes     / power(1024, 3), 3)    AS stage_gb,
    round(failsafe_bytes  / power(1024, 3), 3)    AS failsafe_gb
FROM snowflake.account_usage.storage_usage
WHERE usage_date > dateadd('day', -30, current_date());

-- ----------------------------------------------------------------------------
-- 7) Fraîcheur du pipeline (TEMPS RÉEL — lit les tables du projet, pas
--    ACCOUNT_USAGE) : dernier chargement + volumétrie par couche.
--    count(*) sans filtre = métadonnées micro-partitions → quasi gratuit.
--    NB loaded_at : COPY INTO n'applique PAS le DEFAULT d'une colonne absente
--    du Parquet → loaded_at est NULL tant que l'ingestion ne le mappe pas via
--    INCLUDE_METADATA (comme source_file). Fallback : last_altered de la table.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_pipeline_freshness AS
SELECT
    coalesce(
        (SELECT max(loaded_at) FROM nyc_taxi_db.raw.yellow_taxi_trips),
        (SELECT max(last_altered) FROM nyc_taxi_db.information_schema.tables
          WHERE table_schema = 'RAW' AND table_name = 'YELLOW_TAXI_TRIPS')
    )                                                                   AS last_load_at,
    datediff('hour',
        coalesce(
            (SELECT max(loaded_at) FROM nyc_taxi_db.raw.yellow_taxi_trips),
            (SELECT max(last_altered) FROM nyc_taxi_db.information_schema.tables
              WHERE table_schema = 'RAW' AND table_name = 'YELLOW_TAXI_TRIPS')),
        current_timestamp())                                            AS hours_since_last_load,
    (SELECT count(*) FROM nyc_taxi_db.raw.yellow_taxi_trips)            AS raw_rows,
    (SELECT count(*) FROM nyc_taxi_db.staging.int_trip_metrics)         AS staging_metric_rows,
    (SELECT count(*) FROM nyc_taxi_db.final.daily_summary)              AS final_daily_rows,
    (SELECT count(*) FROM nyc_taxi_db.final.zone_analysis)              AS final_zone_rows,
    (SELECT count(*) FROM nyc_taxi_db.final.hourly_patterns)            AS final_hourly_rows,
    current_timestamp()                                                 AS checked_at;

-- ----------------------------------------------------------------------------
-- Contrôle.
-- ----------------------------------------------------------------------------
SHOW VIEWS IN SCHEMA NYC_TAXI_DB.MONITORING;
