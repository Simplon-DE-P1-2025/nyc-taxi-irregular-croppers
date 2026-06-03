-- stg_yellow_taxi_trips — nettoyage / filtres qualité (issue #13)

with source as (

    select * from {{ source('nyc_taxi', 'yellow_taxi_trips') }}

),

nettoye as (

    select
        -- identifiants et dimensions (renommes snake_case)
        vendorid as vendor_id,
        tpep_pickup_datetime as pickup_datetime,
        tpep_dropoff_datetime as dropoff_datetime,
        case when passenger_count is null or passenger_count = 0 then 1
             else passenger_count end as passenger_count,
        trip_distance,
        ratecodeid as rate_code_id,
        store_and_fwd_flag,
        pulocationid as pickup_location_id,
        dolocationid as dropoff_location_id,
        payment_type,

        -- montants
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

        -- libelles dictionnaire TLC (mars 2025)
        case vendorid
            when 1 then 'Creative Mobile Technologies'
            when 2 then 'Curb Mobility'
            when 6 then 'Myle Technologies'
            when 7 then 'Helix'
            else 'Autre/Inconnu'
        end as vendor_libelle,

        case ratecodeid
            when 1 then 'Standard rate'
            when 2 then 'JFK'
            when 3 then 'Newark'
            when 4 then 'Nassau or Westchester'
            when 5 then 'Negotiated fare'
            when 6 then 'Group ride'
            when 99 then 'Null/unknown'
            else 'Inconnu'
        end as rate_code_libelle,

        case payment_type
            when 0 then 'Flex Fare trip'
            when 1 then 'Credit card'
            when 2 then 'Cash'
            when 3 then 'No charge'
            when 4 then 'Dispute'
            when 5 then 'Unknown'
            when 6 then 'Voided trip'
            else 'Autre'
        end as payment_libelle,

        -- metadonnees d'ingestion
        source_file,
        loaded_at

    from source

    where
        -- montants (fare >= 0 : on accepte les courses gratuites type 'No charge')
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

        -- code tarif valide (1 a 6 ; 99 = null/unknown rejete)
        and ratecodeid between 1 and 6

        -- colonnes critiques non nulles + periode projet
        and pulocationid is not null
        and dolocationid is not null
        and tpep_pickup_datetime >= '2024-01-01'
        and tpep_pickup_datetime <  '2026-01-01'

)

select * from nettoye