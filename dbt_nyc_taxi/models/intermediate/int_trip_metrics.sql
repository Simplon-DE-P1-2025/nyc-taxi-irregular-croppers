-- int_trip_metrics — durée, vitesse, % pourboire, dimensions temporelles (issue #15)
-- Squelette : contrat de nom posé pour la CI (dbt parse) et le DAG. À implémenter.
-- int_trip_metrics — durée, vitesse, % pourboire, dimensions temporelles (issue #15)

-- int_trip_metrics — durée, vitesse, % pourboire, dimensions temporelles (issue #15)

{{ config(materialized='table') }}

with stg as (

    select * from {{ ref('stg_yellow_taxi_trips') }}

),

base as (

    select
        *,
        -- duree precise : calcul en secondes puis conversion en minutes decimales
        -- (un trajet de 45s = 0.75 min, pas 0 → vitesse calculable, aucune ligne perdue)
        round(datediff('second', pickup_datetime, dropoff_datetime) / 60.0, 2) as trip_duration_minutes
    from stg

),

metriques as (

    select
        *,

        -- vitesse moyenne mph (nullif = securite, ne devrait jamais declencher apres #13)
        round(trip_distance / nullif(trip_duration_minutes / 60.0, 0), 2) as avg_speed_mph,

        -- taux de pourboire % (null si fare = 0, course gratuite acceptee en #13)
        case when payment_type = 1
             then round(tip_amount / nullif(fare_amount, 0) * 100, 2)
        end as tip_percentage,

        -- dimensions temporelles
        hour(pickup_datetime)  as pickup_hour,
        day(pickup_datetime)   as pickup_day,
        month(pickup_datetime) as pickup_month,
        dayname(pickup_datetime) as day_of_week,

        -- categorie de distance (seuils a valider en equipe)
        case
            when trip_distance < 2 then 'courte'
            when trip_distance < 10 then 'moyenne'
            else 'longue'
        end as categorie_distance,

        -- periode de la journee (decoupage a valider en equipe)
        case
            when hour(pickup_datetime) between 0 and 5  then 'nuit'
            when hour(pickup_datetime) between 6 and 11 then 'matin'
            when hour(pickup_datetime) between 12 and 17 then 'apres-midi'
            else 'soir'
        end as periode_journee

    from base

)

select * from metriques