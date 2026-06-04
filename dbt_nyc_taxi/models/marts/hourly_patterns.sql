-- hourly_patterns — KPIs par heure, heures de pointe (sprint J3)
-- Squelette : contrat de nom posé pour la CI (dbt parse) et le DAG. À implémenter.
-- hourly_patterns — Analyse des heures de pointe 
{{ config(
    materialized='table'
) }}

SELECT
    pickup_hour,
    COUNT(*) AS trip_count,
    AVG(trip_distance) AS avg_distance,
    AVG(total_amount) AS avg_revenue,
    AVG(avg_speed_mph) AS avg_speed
FROM {{ ref('int_trip_metrics') }}
GROUP BY 1