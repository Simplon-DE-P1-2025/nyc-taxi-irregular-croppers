-- stg_yellow_taxi_trips — nettoyage / filtres qualité (issue #13)

with source as (

    select * from {{ source('nyc_taxi', 'yellow_taxi_trips') }}

),

nettoye as (

    select
        vendorid,
        tpep_pickup_datetime,
        tpep_dropoff_datetime,
        case when passenger_count is null or passenger_count = 0 then 1
             else passenger_count end as passenger_count,
        trip_distance,
        ratecodeid,
        store_and_fwd_flag,
        pulocationid,
        dolocationid,
        payment_type,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        improvement_surcharge,
        total_amount,
        congestion_surcharge,
        airport_fee,
        cbd_congestion_fee,
        source_file,
        loaded_at

    from source

    where
        -- montants
        fare_amount >= 0
        and total_amount > 0
        and tip_amount >= 0 


        -- distance (borne haute = anti-aberration, pas seuil de normalite)
        and trip_distance > 0
        and trip_distance < 100

        -- coherence temporelle (depart avant arrivee)
        and tpep_pickup_datetime < tpep_dropoff_datetime

        -- duree plausible (plafond 5h = anti-aberration, large pour les bouchons)
        and datediff('minute', tpep_pickup_datetime, tpep_dropoff_datetime) <= 300

        -- code tarif valide (1 a 6, dictionnaire TLC)
        and ratecodeid between 1 and 6

        -- colonnes critiques non nulles
        and pulocationid is not null
        and dolocationid is not null
        and tpep_pickup_datetime >= '2024-01-01'
        and tpep_pickup_datetime <  '2026-01-01'

)

select * from nettoye
