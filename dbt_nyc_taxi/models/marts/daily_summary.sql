-- daily_summary — KPIs par jour 
{{ config(
    materialized='table'
) }}

SELECT
    date(pickup_datetime)::DATE AS trip_date,
    COUNT(*) AS trip_count,
    round(AVG(trip_distance), 2) AS avg_distance,
    SUM(total_amount) AS total_revenue,
    ROUND(SUM(total_amount) / COUNT(*), 2) AS avg_revenue_per_trip,
    ROUND(AVG(tip_amount), 2) AS avg_tip
FROM {{ ref('int_trip_metrics') }}
GROUP BY 1