-- hourly_patterns — KPIs par heure, heures de pointe (sprint J3)
-- Squelette : contrat de nom posé pour la CI (dbt parse) et le DAG. À implémenter.
-- hourly_patterns — Analyse des heures de pointe 
{{ config(
    materialized='table'
) }}

SELECT
    pickup_hour,
    COUNT(*) AS trip_count,
    round(AVG(trip_distance),2) AS avg_distance,
    ROUND(AVG(total_amount)) AS avg_revenue,
    round(sum(trip_distance) / nullif(sum(trip_duration_minutes) / 60.0, 0), 2) as avg_speed
FROM {{ ref('int_trip_metrics') }}
GROUP BY 1