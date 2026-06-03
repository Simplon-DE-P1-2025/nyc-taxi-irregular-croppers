# Architecture cible — NYC Taxi (spec consolidée)

> Source canonique : https://github.com/gsoulat/formation-data-engineer/blob/main/99-Brief/Snowflake+Dbt/nyc_taxi_dbt_pipeline.md
> Ce doc consolide la spec **imposée** + les **points d'attention** repérés (section ⚠️ en bas — à lire avant de coder).

## Dataset
- NYC **Yellow** Taxi Trip Data, **~40 M trajets**, **2024 + début 2025**, Parquet mensuels.
- Source : `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet`
- Data dictionary : NYC TLC.

## Objets Snowflake imposés (noms exacts)
```sql
CREATE WAREHOUSE NYC_TAXI_WH WITH WAREHOUSE_SIZE = 'MEDIUM' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;
CREATE DATABASE NYC_TAXI_DB;
CREATE SCHEMA NYC_TAXI_DB.RAW;
CREATE SCHEMA NYC_TAXI_DB.STAGING;
CREATE SCHEMA NYC_TAXI_DB.FINAL;
```
Architecture en 3 couches : **RAW** (brut) → **STAGING** (nettoyé + métriques) → **FINAL** (tables analytiques).

## Table RAW (DDL imposé)
`NYC_TAXI_DB.RAW.yellow_taxi_trips` — 21 colonnes (tpep_pickup/dropoff_datetime, passenger_count,
trip_distance, pu/do_location_id, payment_type, fare/tip/total_amount, congestion_surcharge,
airport_fee, …) + `loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`. Voir DDL complet dans la consigne.

## Règles de nettoyage (→ STAGING.clean_trips)
- `fare_amount > 0` ET `total_amount > 0` ET `tip_amount >= 0`
- `tpep_pickup_datetime < tpep_dropoff_datetime`
- `trip_distance BETWEEN 0.1 AND 100`
- `pu_location_id` / `do_location_id` NOT NULL
- `passenger_count > 0`
> Problèmes connus du dataset : 15,54 % de valeurs manquantes, 4,15 % de montants négatifs,
> 2,62 % de trajets distance nulle, outliers > 1000 miles.

## Métriques calculées (STAGING)
- `trip_duration_minutes` = DATEDIFF(MINUTE, pickup, dropoff)
- `avg_speed_mph` = distance / durée * 60
- `tip_percentage` = tip / fare * 100
- Dimensions temporelles : pickup_hour / day / month, day_of_week
- `distance_category` (Short ≤1 / Medium 1-5 / Long 5-10 / Very Long >10)
- `time_period` (Morning Rush 6-9 / Daytime 10-15 / Evening Rush 16-19 / Evening 20-23 / Night)
- `day_type` (Weekend / Weekday)

## Tables FINAL attendues
- `FINAL.daily_summary` — par jour : nb trajets, distance moy, revenu total/moyen, tip moyen
- `FINAL.zone_analysis` — par `pu_location_id` : trajets, distance/revenu moyen, revenu total
- `FINAL.hourly_patterns` — par heure : nb trajets, distance/revenu/vitesse moyens

## KPIs minimum
Nb trajets mensuels · revenu moyen/trajet · distance moyenne · top 10 zones de pickup · heures de pointe.

## Structure dbt (RAW→STAGING→FINAL mappé sur dbt)
```
models/
  staging/      stg_yellow_taxi_trips.sql      (view ; filtres de nettoyage)
  intermediate/ int_trip_metrics.sql           (table ; métriques + catégorisations)
  marts/        fact_trips.sql, daily_summary.sql, zone_analysis.sql, hourly_patterns.sql
```
- `staging` = view, `intermediate` + `marts` = table (cf. `dbt_project.yml`).
- `sources.yml` : source `nyc_taxi` → `NYC_TAXI_DB.RAW.yellow_taxi_trips`.
- Tests : `not_null`, `dbt_utils.expression_is_true` (⇒ besoin du package **dbt_utils**).

## Orchestration GitHub Actions (obligatoire)
Workflow `.github/workflows/nyc_taxi_pipeline.yml` : checkout → setup Python → install dbt →
générer `profiles.yml` depuis les **secrets** → `dbt debug` → download data → `dbt run` →
`dbt test` → `dbt docs generate` → upload artifacts → notif Slack si échec.
Déclencheurs : `workflow_dispatch` + `schedule` (cron mensuel).

---

## ⚠️ POINTS D'ATTENTION (pièges repérés — à corriger vs le brief)

1. **L'external stage `URL='s3://d37ci6vzurychx.cloudfront.net/...'` ne marchera PAS tel quel.**
   Ce n'est pas un bucket S3 mais un **CDN CloudFront en HTTPS**. Snowflake ne peut pas y faire
   un external stage S3. ➜ Chemins fiables :
   - **(recommandé)** télécharger le Parquet (Python) → `PUT` dans un **stage interne** → `COPY INTO`,
     ou charger via `write_pandas` / connecteur Python ;
   - ou réutiliser **notre combo Azure Blob + SAS** (déjà testé) comme landing zone → external stage Azure.

2. **Auth CI : utiliser une PAIRE DE CLÉS, pas un mot de passe.**
   Le workflow du brief met `password: ${{ secrets... }}`. Or Snowflake **déprécie l'auth
   mot-de-passe seul** (MFA imposée, connexions programmatiques bloquées). Pour GitHub Actions,
   configurer la **key-pair authentication** (clé RSA en secret) → seul moyen fiable en CI.

3. **Version dbt du brief obsolète.** Le workflow épingle `dbt-snowflake==1.5.0`. On est en **1.11**.
   Utiliser une version récente (cohérente avec notre `uv.lock`).

4. **Test `relationships` douteux dans `schema.yml`.** Le brief teste une relation sur un timestamp
   vers la source — peu pertinent et lent sur 40 M lignes. À remplacer par des tests utiles
   (unicité d'une clé de trajet, `accepted_values` sur payment_type, etc.).

5. **Coûts trial.** Warehouse **MEDIUM = 4 crédits/h**. Sur un trial ($400/30 j), faire les
   gros `COPY`/`dbt run` en MEDIUM puis **redescendre en XSMALL** pour le dev. `AUTO_SUSPEND=60`
   est indispensable. (Volet « estimation des coûts » → cf. `docs/monitoring-snowflake.md`.)

6. **API ≠ consigne canonique.** Un des documents mentionne « exploitation via une API » mais la
   consigne détaillée parle de **Dashboard** (Streamlit), pas d'API. ➜ **À clarifier avec le formateur**
   avant d'investir dans une FastAPI. Le livrable sûr = dashboard viz (optionnel) + rapport.
