-- zone_analysis — KPIs par zone de pickup (issue #30)
-- Grain --> 1 ligne = 1 pu_location_id

{{ config(materialized='table') }}

with source as (

    select * from {{ ref('int_trip_metrics') }}

),

zones as (

    select * from {{ ref('taxi_zone_lookup') }}

)

select
    s.pu_location_id,
    z.borough,
    z.zone,
    z.service_zone,
    count(*)                       as total_trips,
    round(avg(s.trip_distance), 2) as avg_distance,
    round(avg(s.total_amount), 2)  as avg_revenue,
    round(sum(s.total_amount), 2)  as total_revenue

from source s
left join zones z
    on s.pu_location_id = z.locationid

group by
    s.pu_location_id,
    z.borough,
    z.zone,
    z.service_zone
