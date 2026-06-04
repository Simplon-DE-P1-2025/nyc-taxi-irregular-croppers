# Transformations dbt — choix & justifications

> But de ce doc : permettre à l'équipe de **comprendre les choix de modélisation** et de
> **reprendre le travail** sans rétro-ingénierie. Chaque décision non triviale est expliquée
> (le *pourquoi*, pas seulement le *quoi*). Complète les descriptions dbt (`_models.yml` →
> `dbt docs`) par le contexte narratif.

## Vue d'ensemble — 3 couches mappées sur dbt

```
RAW (source)                STAGING                         FINAL
yellow_taxi_trips  ──►  stg_yellow_taxi_trips  ──►  int_trip_metrics  ──►  daily_summary
   (table brute)          (view, nettoyage)        (table, métriques)      zone_analysis
                                                                            hourly_patterns
```

| Modèle | Dossier | Matérialisation | Schéma Snowflake |
|---|---|---|---|
| `stg_yellow_taxi_trips` | `staging/` | **view** | `STAGING` |
| `int_trip_metrics` | `intermediate/` | **table** | `STAGING` |
| `daily_summary` / `zone_analysis` / `hourly_patterns` | `marts/` | **table** | `FINAL` |

> ℹ️ L'intermediate est matérialisé dans le schéma **STAGING** (et non un schéma `INTERMEDIATE`
> dédié) parce que l'architecture imposée ne prévoit que **3 schémas** : `RAW` / `STAGING` / `FINAL`.

---

## 1. `stg_yellow_taxi_trips` — nettoyage (couche STAGING)

Vue qui applique les **filtres qualité** du brief, confirmés/chiffrés par l'EDA (~13–14 % des
lignes écartées, cf. `docs/exploration-donnees.md`).

**Filtres appliqués :**
- `fare_amount > 0`, `total_amount > 0`, `tip_amount >= 0` (montants cohérents)
- `tpep_pickup_datetime < tpep_dropoff_datetime` (chronologie)
- `trip_distance between 0.1 and 100` (anti distance nulle / outliers > 100 mi)
- `pu_location_id` / `do_location_id` NOT NULL (zones obligatoires)

**Choix expliqués :**
- **On garde toutes les composantes tarifaires** (`extra, mta_tax, tolls_amount,
  improvement_surcharge, congestion_surcharge, airport_fee, cbd_congestion_fee`) **et `loaded_at`**.
  Pourquoi : permettre une future **décomposition du revenu** et garder la porte ouverte à un
  **modèle incrémental** (clé sur `loaded_at`). Coût quasi nul, on évite de se fermer des options.
- **`passenger_count`** : on écarte les **0 explicites** (erreurs probables) mais on **conserve
  les NULL** (`passenger_count is null or passenger_count > 0`) — un trajet sans nombre de
  passagers reste valide pour les KPIs distance/revenu.
- **Garde-fou plage temporelle** `>= 2024-01-01 and < 2026-01-01` : les fichiers TLC contiennent
  des **timestamps aberrants** (années 2002, 2098…). Sans ce filtre, `daily_summary` produirait
  des lignes parasites pour des dates farfelues.
- **Schema drift** : `cbd_congestion_fee` n'existe qu'à partir de 2025 → nullable avant.
- **Renommage snake_case** : les colonnes « collées » de la source (`VendorID`, `RatecodeID`,
  `PULocationID`, `DOLocationID`) sont aliasées en sortie de staging (`vendor_id`, `ratecode_id`,
  `pu_location_id`, `do_location_id`). La couche **RAW garde les noms TLC d'origine** ; le snake_case
  est la **convention de l'aval** (staging → intermediate → marts). C'est pour ça que `_sources.yml`
  et le DDL RAW restent en PascalCase, mais que tout le reste est en snake_case.

---

## 2. `int_trip_metrics` — métriques & catégorisations (couche STAGING)

Table enrichie : durée, vitesse, % pourboire, dimensions et catégories temporelles.

**Choix expliqués :**
- **Durée en secondes puis convertie** (`datediff('second', …) / 60.0`) plutôt qu'en minutes
  entières. Pourquoi : `datediff('minute')` vaut **0** pour un trajet dans la même minute
  d'horloge → division par zéro → vitesse NULL → trajet **supprimé silencieusement**. La version
  en secondes donne une durée fractionnaire correcte et préserve les trajets courts.
- **Vitesse calculée une seule fois** dans un CTE (`with_speed`) puis filtrée — au lieu de
  recalculer l'expression dans le `SELECT` *et* le `WHERE` (DRY + Snowflake ne calcule qu'une fois).
- **`dayofweekiso()`** (1=lundi … 7=dimanche) plutôt que `dayofweek()`. Pourquoi : `dayofweek()`
  dépend du paramètre de session **`WEEK_START`** → la classification week-end serait fragile.
  ISO est **déterministe**. Week-end = `in (6, 7)`.
- **`tip_percentage` calculé uniquement pour `payment_type = 1` (carte), NULL sinon.** Pourquoi :
  dans la source TLC, les **pourboires ne sont enregistrés que pour les paiements carte** ; en
  espèces `tip_amount = 0`. Calculer le % sur tous les trajets sous-estimerait structurellement
  le pourboire. NULL = « non mesurable » (pas `not_null` côté tests).
- **Garde-fou vitesse `<= 100 mph`** sur la colonne calculée (EDA : ~0,03 % de vitesses aberrantes).

---

## 3. Marts (couche FINAL) — tables analytiques pour les KPIs

- **`daily_summary`** — 1 ligne/jour : `trip_count`, `avg_distance`, `total_revenue`,
  `avg_revenue_per_trip`, `avg_tip`.
- **`zone_analysis`** — 1 ligne/`pu_location_id` : volume, distance/revenu moyens, revenu total
  (KPI top 10 zones). *TODO restitution : joindre le lookup TLC (`taxi_zone_lookup`) pour exposer
  Borough/Zone au lieu des ID bruts.*
- **`hourly_patterns`** — 1 ligne/heure (0–23) : volume, distance/revenu moyens, vitesse moyenne.

**Choix expliqués :**
- **Vitesse moyenne horaire = vitesse de FLUX pondérée** : `sum(trip_distance) /
  sum(trip_duration_minutes)/60`. Pourquoi : `avg(avg_speed_mph)` (moyenne des vitesses par
  trajet) est **statistiquement faux** — un trajet court y pèse autant qu'un long. La pondération
  par distance/durée totales donne la vraie vitesse moyenne de l'heure.
- **Pas d'`order by` dans les modèles** : sur une table matérialisée, l'ordre n'est pas garanti au
  stockage (re-trié à la lecture) et le tri ajoute un coût au build. Le tri est l'affaire de la
  couche restitution.

---

## 4. Matérialisation : full rebuild (table) — choix assumé

Tout est en **`table` / `view`**, **pas en incrémental**. Décision et raisons :

- **L'incrémental sur des agrégats est un piège** : les marts agrègent par jour/heure/zone. Un
  append naïf par `loaded_at` **double-compterait** dès qu'un nouveau batch touche un grain
  existant (il faut un `merge` + re-agrégation des partitions → complexe et source de bugs silencieux).
- **Gain quasi nul ici** : dataset quasi figé (2024 + début 2025) + run **mensuel** → on n'amortit
  pas la complexité. Un full run = un scan ~40 M + `group by` simples = quelques minutes de warehouse.
- **Soutenance** : un DAG `view → table → table` s'explique en 30 s ; l'incrémental ajoute de la
  plomberie à démontrer.

**Porte laissée ouverte** : `loaded_at` est conservé en staging. Si le coût devient un problème,
la **seule** cible rentable serait `int_trip_metrics` en incrémental (relation 1:1, append sûr par
`loaded_at`) en **gardant les marts en full table** (agrégation rapide, zéro risque de double-compte).

---

## 5. Tests (qualité)

| Couche | Tests |
|---|---|
| staging | `not_null` (montants, datetime, zones), `accepted_values` sur `payment_type` |
| intermediate | `accepted_range` sur `trip_duration_minutes` (> 0) et `avg_speed_mph` (0–100, **garde de non-régression**) ; `tip_percentage >= 0` (NULL toléré) |
| marts | `unique` + `not_null` sur les grains (`trip_date`, `pickup_hour`, `pu_location_id`), `accepted_range` (`trip_count` > 0, `pickup_hour` ∈ [0,23]) |

Le test `avg_speed_mph <= 100` est volontairement « tautologique » au regard du filtre du modèle :
il sert de **garde-fou** si quelqu'un retire le `WHERE` un jour.

---

## 6. Réserves connues (à garder en tête pour le rapport d'analyse)

- **`avg_tip` (daily_summary)** = `avg(tip_amount)` sur **tous** les trajets, donc inclut les
  paiements espèces (= 0). À ne pas confondre avec `tip_percentage` (carte uniquement). Mesures
  cohérentes mais de **périmètres différents** — à préciser à la lecture.
- **`tip_percentage` non plafonné** : un pourboire > course donne > 100 % (rare).
- **Trajets « sous la seconde »** : si pickup/dropoff diffèrent de < 1 s, la durée arrondit à 0 →
  trajet écarté. Cas marginal, probablement de la mauvaise donnée.

---

## 7. Comment exécuter / reprendre

```bash
cd dbt_nyc_taxi
# Auth Snowflake = clé RSA (cf. docs/onboarding.md) — exporter les 3 variables :
export SNOWFLAKE_ACCOUNT="<TON_ORG-TON_ACCOUNT>"
export SNOWFLAKE_USER="<TON_USER>"
export SNOWFLAKE_PRIVATE_KEY_PATH="$HOME/.snowflake/nyc_taxi_key.p8"

uv run dbt deps
uv run dbt build           # staging → intermediate → marts → tests (contre le seed ou les données réelles)
uv run dbt docs generate   # documentation (reprend les descriptions des _models.yml)
```

La CI valide la compilation hors-ligne (`dbt parse`) sur chaque PR, sans connexion Snowflake.
