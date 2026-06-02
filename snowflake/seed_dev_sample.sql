-- ============================================================================
--  seed_dev_sample.sql — JEU DE DONNÉES DE DÉVELOPPEMENT (fixture)
--
--  But : permettre de développer/tester la couche dbt (staging → marts) SANS
--  attendre la vraie ingestion (#4). Ce N'EST PAS de la vraie donnée : ce sont
--  ~15 lignes fabriquées, choisies pour exercer les règles de nettoyage.
--
--  À jouer APRÈS snowflake/01_setup_infra.sql, sur ton compte de dev :
--      snow sql -c projet7 -f snowflake/seed_dev_sample.sql
--
--  ⚠️ DEV ONLY. Le TRUNCATE vide la table : à ne jamais lancer sur un compte
--     qui contient de la vraie donnée ingérée.
--
--  Contenu : 10 lignes PROPRES (doivent survivre aux filtres de #13) + 5 lignes
--  SALES (doivent être éliminées). Donc après le staging : 15 en entrée → 10 propres.
--  Couvre : vendors 1/2/6/7, payment_type 1/2, ratecode 1/2/99, store_and_fwd Y/N,
--  drift 2024 (cbd_congestion_fee NULL) vs 2025 (renseigné), heures et zones variées.
-- ============================================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE NYC_TAXI_WH;
USE DATABASE  NYC_TAXI_DB;
USE SCHEMA    RAW;

TRUNCATE TABLE IF EXISTS RAW.yellow_taxi_trips;

INSERT INTO RAW.yellow_taxi_trips
  (VendorID, tpep_pickup_datetime, tpep_dropoff_datetime, passenger_count, trip_distance,
   RatecodeID, store_and_fwd_flag, PULocationID, DOLocationID, payment_type,
   fare_amount, extra, mta_tax, tip_amount, tolls_amount, improvement_surcharge,
   total_amount, congestion_surcharge, Airport_fee, cbd_congestion_fee, source_file)
VALUES
  -- ───────── 10 lignes PROPRES (attendues après nettoyage) ─────────
  (1, '2024-01-15 08:30:00', '2024-01-15 08:52:00', 1, 3.20, 1, 'N', 142, 236, 1,
     14.20, 1.00, 0.50, 3.50, 0.00, 1.00, 22.70, 2.50, 0.00, NULL, 'dev_sample'),
  (2, '2024-01-20 18:05:00', '2024-01-20 18:40:00', 2, 8.50, 1, 'N', 138, 170, 2,
     32.00, 1.00, 0.50, 0.00, 6.55, 1.00, 43.55, 2.50, 0.00, NULL, 'dev_sample'),
  (1, '2024-02-10 14:00:00', '2024-02-10 14:48:00', 1, 17.30, 2, 'N', 132, 230, 1,
     70.00, 0.00, 0.50, 15.00, 6.94, 1.00, 97.69, 2.50, 1.75, NULL, 'dev_sample'),
  (6, '2025-01-08 09:15:00', '2025-01-08 09:35:00', 1, 2.10, 1, 'N', 161, 162, 1,
     11.40, 1.00, 0.50, 2.80, 0.00, 1.00, 19.95, 2.50, 0.00, 0.75, 'dev_sample'),
  (7, '2025-02-14 22:10:00', '2025-02-14 22:33:00', 3, 4.60, 1, 'N', 79, 148, 2,
     18.40, 1.00, 0.50, 0.00, 0.00, 1.00, 24.65, 2.50, 0.00, 0.75, 'dev_sample'),
  (2, '2024-03-02 02:30:00', '2024-03-02 02:50:00', 1, 5.00, 1, 'N', 48, 68, 1,
     20.50, 1.00, 0.50, 4.00, 0.00, 1.00, 29.50, 2.50, 0.00, NULL, 'dev_sample'),
  (1, '2025-03-19 12:00:00', '2025-03-19 12:25:00', 2, 6.30, 1, 'N', 230, 142, 1,
     24.00, 0.00, 0.50, 0.00, 0.00, 1.00, 28.75, 2.50, 0.00, 0.75, 'dev_sample'),
  (6, '2024-01-25 16:45:00', '2024-01-25 17:30:00', 1, 12.00, 1, 'N', 132, 48, 1,
     48.00, 1.00, 0.50, 10.00, 6.94, 1.00, 69.94, 2.50, 0.00, NULL, 'dev_sample'),
  (7, '2025-01-30 07:50:00', '2025-01-30 08:20:00', 1, 9.10, 99, 'N', 100, 200, 1,
     30.00, 1.00, 0.50, 5.00, 0.00, 1.00, 40.75, 2.50, 0.00, 0.75, 'dev_sample'),
  (2, '2024-02-18 19:20:00', '2024-02-18 19:55:00', 4, 7.40, 1, 'Y', 114, 79, 2,
     28.00, 1.00, 0.50, 0.00, 0.00, 1.00, 33.00, 2.50, 0.00, NULL, 'dev_sample'),

  -- ───────── 5 lignes SALES (doivent être éliminées par #13) ─────────
  -- fare_amount <= 0
  (1, '2024-01-16 10:00:00', '2024-01-16 10:20:00', 1, 3.00, 1, 'N', 142, 236, 1,
     -5.00, 0.00, 0.50, 0.00, 0.00, 1.00, -1.00, 2.50, 0.00, NULL, 'dev_sample'),
  -- total_amount <= 0
  (2, '2024-01-17 11:00:00', '2024-01-17 11:15:00', 1, 2.00, 1, 'N', 48, 68, 2,
     0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, 'dev_sample'),
  -- trip_distance = 0
  (1, '2024-01-18 12:00:00', '2024-01-18 12:05:00', 1, 0.00, 1, 'N', 142, 142, 1,
     5.00, 0.00, 0.50, 0.00, 0.00, 1.00, 9.00, 2.50, 0.00, NULL, 'dev_sample'),
  -- passenger_count NULL
  (6, '2025-01-19 13:00:00', '2025-01-19 13:30:00', NULL, 5.50, 1, 'N', 161, 162, 1,
     22.00, 1.00, 0.50, 3.00, 0.00, 1.00, 30.75, 2.50, 0.00, 0.75, 'dev_sample'),
  -- pickup >= dropoff (incohérence temporelle)
  (2, '2024-02-20 15:30:00', '2024-02-20 15:10:00', 1, 4.00, 1, 'N', 79, 148, 1,
     16.00, 1.00, 0.50, 2.00, 0.00, 1.00, 23.00, 2.50, 0.00, NULL, 'dev_sample');

-- Contrôle : 15 lignes insérées (10 propres + 5 sales).
-- NB : Snowflake n'a pas COUNT(*) FILTER (...) → on utilise COUNT_IF(...).
SELECT COUNT(*) AS lignes_inserees,
       COUNT_IF(fare_amount > 0 AND total_amount > 0 AND trip_distance > 0
                AND passenger_count IS NOT NULL
                AND tpep_pickup_datetime < tpep_dropoff_datetime) AS propres_attendues
FROM RAW.yellow_taxi_trips;
