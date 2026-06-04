-- daily_summary — KPIs par jour 
{{ config(
    materialized='table'
) }}

SELECT
    date(pickup_datetime)::DATE AS trip_date,
    COUNT(*) AS trip_count,
    AVG(trip_distance) AS avg_distance,
    SUM(total_amount) AS total_revenue,
    SUM(total_amount) / COUNT(*) AS avg_revenue_per_trip,
    AVG(tip_amount) AS avg_tip
FROM {{ ref('int_trip_metrics') }}
GROUP BY 1