{{ config(materialized='view', schema='STAGING', enabled=(target.type == 'duckdb')) }}

-- ====================================================================
-- SPIKE DuckDB hybride — modèle STANDALONE (ne tourne QUE sur target duckdb).
-- Reproduit la logique de stg_yellow_taxi_trips (couche STAGING : nettoyage du brief)
-- en SQL PORTABLE, mais en lisant un Parquet LOCAL au lieu de la source Snowflake RAW.
--
-- Pourquoi un modèle séparé plutôt que d'adapter stg_yellow_taxi_trips ?
--   La friction documentée : source('nyc_taxi','yellow_taxi_trips') pointe vers
--   NYC_TAXI_DB.RAW (Snowflake). La rediriger « en place » imposerait un external_location
--   dbt-duckdb dans _sources.yml, qui casserait la résolution Snowflake d'origine.
--   On isole donc la redirection ici (enabled seulement sur duckdb) → la prod reste intacte.
--
-- Portabilité illustrée :
--   - dbt_utils.datediff(...) au lieu de date_diff() natif DuckDB / DATEDIFF() Snowflake.
--   - dbt_utils.date_trunc(...) au lieu de date_trunc() / DATE_TRUNC().
--   - identifiants PascalCase du Parquet ("VendorID", "RatecodeID", "PULocationID",
--     "DOLocationID", "Airport_fee") explicitement aliasés en snake_case → mêmes noms
--     de colonnes que le modèle Snowflake (qui, lui, reçoit déjà du snake_case via COPY INTO).
-- ====================================================================

{% set parquet_path = var('parquet_path', 'data/raw/yellow_tripdata_2024-01.parquet') %}

with raw_trips as (
    -- read_parquet : équivalent DuckDB d'un SELECT sur la table RAW Snowflake.
    -- (atout DuckDB : aucune ingestion préalable, lecture directe du fichier)
    select * from read_parquet('{{ parquet_path }}')
)

select
    "VendorID"                                                              as vendorid,
    tpep_pickup_datetime,
    tpep_dropoff_datetime,
    passenger_count,
    trip_distance,
    "RatecodeID"                                                            as ratecodeid,
    store_and_fwd_flag,
    "PULocationID"                                                          as pulocationid,
    "DOLocationID"                                                          as dolocationid,
    payment_type,
    fare_amount,
    tip_amount,
    total_amount,

    -- Colonnes calculées en SQL PORTABLE (macros cross-db à dispatch DuckDB↔Snowflake).
    -- NB friction : depuis dbt_utils 1.0, datediff/date_trunc ont migré de dbt_utils.* vers
    -- le namespace dbt-core dbt.* → on appelle dbt.datediff / dbt.date_trunc (PAS dbt_utils.datediff).
    {{ dbt.datediff('tpep_pickup_datetime', 'tpep_dropoff_datetime', 'minute') }} as trip_duration_min,
    {{ dbt.date_trunc('day', 'tpep_pickup_datetime') }}                           as pickup_day

from raw_trips
where fare_amount > 0
  and total_amount > 0
  and tip_amount >= 0
  and tpep_pickup_datetime < tpep_dropoff_datetime
  and trip_distance between 0.1 and 100
  and "PULocationID" is not null
  and "DOLocationID" is not null
  and passenger_count > 0
