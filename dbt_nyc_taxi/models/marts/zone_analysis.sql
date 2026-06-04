-- zone_analysis — KPIs par zone de pickup, top 10 (issue #30)
-- Grain --> 1 ligne = 1 pu_location_id

{{ config(materialized='table') }}

with source as (

    select * from {{ ref('int_trip_metrics') }}

)

select
    pu_location_id,
    count(*)                           as nb_trajets,
    round(avg(trip_distance), 2)       as distance_moy,
    round(avg(total_amount), 2)        as revenu_moyen,
    round(sum(total_amount), 2)        as revenu_total

from source
group by 1
