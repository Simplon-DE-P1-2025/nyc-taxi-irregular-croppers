# Guide dbt — comprendre et reproduire la démarche

> Pour l'équipe. Objectif : comprendre **ce qu'est dbt**, **comment il s'insère dans notre flux**,
> et **refaire la démarche pas à pas** pour obtenir les mêmes modèles. Complète
> `docs/transformations-dbt.md` (le *pourquoi* des choix) et `docs/onboarding.md` (l'auth/connexion).

---

## 1. Qu'est-ce que dbt, en 2 minutes

dbt (**data build tool**) sert à **transformer** des données **déjà présentes dans l'entrepôt**
(Snowflake), en SQL. On n'écrit pas de pipeline impératif : on déclare des **modèles** (des `SELECT`),
dbt s'occupe de créer les vues/tables, dans le bon ordre, et de tester.

Concepts clés :

| Concept | C'est quoi | Chez nous |
|---|---|---|
| **source** | une table brute existante, déclarée en YAML | `RAW.yellow_taxi_trips` (`_sources.yml`) |
| **model** | un fichier `.sql` = un `SELECT` → devient une vue ou une table | `stg_…`, `int_…`, les 3 marts |
| **`ref()` / `source()`** | référencer un autre modèle / une source | `from {{ ref('stg_yellow_taxi_trips') }}` |
| **materialization** | `view` (recalcule à la lecture) ou `table` (stockée) | staging=view, int+marts=table |
| **DAG** | dbt déduit l'ordre d'exécution à partir des `ref()` | source → stg → int → marts |
| **tests** | assertions en YAML (`not_null`, `unique`, plages…) | `_models.yml` de chaque couche |
| **seed** | un petit CSV versionné chargé en table | (à venir : `taxi_zone_lookup`) |
| **docs** | site HTML auto-généré à partir des descriptions | `dbt docs generate` |

Le point fort : grâce aux `ref()`, dbt **connaît les dépendances** → il construit dans l'ordre,
parallélise, et sait quoi reconstruire.

---

## 2. Comment dbt s'intègre à NOTRE flux

```
   Parquet TLC          ingestion (Python)        dbt (transformation)         restitution
 (CloudFront)   ──►   PUT stage → COPY INTO   ──►  RAW → STAGING → FINAL   ──►  KPIs / rapport
                                              ▲
                                  GitHub Actions orchestre tout
                                  (auth clé RSA, dbt build mensuel)
```

- **Avant dbt** : l'ingestion charge les Parquet dans `RAW` (table brute). dbt **ne télécharge rien** :
  il part de ce qui est dans Snowflake.
- **dbt** : construit les 3 couches.
  - `RAW` → **`STAGING`** : `stg_yellow_taxi_trips` (vue) nettoie/filtre.
  - **`STAGING`** : `int_trip_metrics` (table) ajoute durée, vitesse, % pourboire, catégories.
  - → **`FINAL`** : `daily_summary`, `zone_analysis`, `hourly_patterns` (tables) = les KPIs.
- **Après dbt** : les tables `FINAL` alimentent l'analyse / le rapport.
- **CI/CD (GitHub Actions)** :
  - sur **chaque PR** → `ci.yml` lance `ruff` + `dbt parse` (validation **hors-ligne**, sans Snowflake) ;
  - dans le **pipeline** → `dbt build` réel (auth **clé RSA**, cf. `docs/onboarding.md`).

> Conséquence pratique : tu peux **développer et tester tes modèles en local** contre le **seed de dev**
> sans attendre l'ingestion réelle.

---

## 3. Les données de base dont tu as besoin

Tu n'as **rien à télécharger manuellement**. Tout est déjà dans le repo / reproductible :

1. **Ton compte Snowflake + ton infra** : suis `docs/onboarding.md` (clé RSA) puis
   ```bash
   snow sql -c projet7 -f snowflake/01_setup_infra.sql   # warehouse, DB, schémas RAW/STAGING/FINAL, table RAW
   ```
2. **Des données pour développer** — deux options :
   - **Seed de dev (recommandé pour démarrer)** : un échantillon déjà versionné.
     ```bash
     snow sql -c projet7 -f snowflake/seed_dev_sample.sql   # remplit RAW.yellow_taxi_trips (~15 lignes)
     ```
     → suffisant pour faire tourner tout le DAG dbt et valider la logique. **DEV ONLY** (fait un TRUNCATE).
   - **Données réelles** : via le script d'ingestion (Parquet → `PUT` → `COPY INTO`). Plus long,
     nécessaire pour les vrais chiffres.

Avec ça, `RAW.yellow_taxi_trips` est peuplée → dbt a de quoi travailler.

---

## 4. La démarche pas à pas (pour arriver au même résultat)

```bash
cd dbt_nyc_taxi

# a) Dépendances dbt (dbt_utils) + variables d'env d'auth (cf. onboarding.md)
uv run dbt deps
export SNOWFLAKE_ACCOUNT="<TON_ORG-TON_ACCOUNT>"
export SNOWFLAKE_USER="<TON_USER>"
export SNOWFLAKE_PRIVATE_KEY_PATH="$HOME/.snowflake/nyc_taxi_key.p8"

# b) Vérifier la connexion + la compilation
uv run dbt debug          # connexion Snowflake OK ?
uv run dbt parse          # le DAG compile ? (c'est ce que fait la CI, en hors-ligne)

# c) Construire de bout en bout (seed → models → tests)
uv run dbt build          # crée STAGING/FINAL sur TON compte, lance les tests

# d) Voir le résultat
#    → tables NYC_TAXI_DB.FINAL.daily_summary / zone_analysis / hourly_patterns
uv run dbt docs generate && uv run dbt docs serve   # documentation interactive (lineage + descriptions)
```

**Ordre de développement des modèles** (logique du DAG — on n'écrit jamais un modèle avant sa dépendance) :
`staging` → `intermediate` → `marts`. Chaque couche a son `.sql` (le `SELECT`) **et** son `_models.yml`
(tests + descriptions).

> `dbt run` ≠ `dbt build` : `run` exécute seulement les modèles. **`build`** enchaîne seed → models →
> tests (+ snapshots). Prends le réflexe **`dbt build`**, surtout quand un seed entre en jeu (cf. §5).

---

## 5. Prochaine étape : enrichir les zones (lookup TLC)

`zone_analysis` sort aujourd'hui des **ID de zone** bruts. On va les rendre lisibles (Borough, nom de
zone) via un **seed** `taxi_zone_lookup`. La démarche détaillée et son impact sont décrits dans
**`docs/plan-zone-lookup-seed.md`** — c'est un bon premier exercice dbt « de bout en bout » (seed +
jointure + test `relationships`).

---

## 6. Où regarder quand on est bloqué

| Question | Doc |
|---|---|
| Me connecter à Snowflake (clé RSA) | `docs/onboarding.md` |
| Pourquoi tel filtre / tel calcul | `docs/transformations-dbt.md` |
| Architecture cible / KPIs imposés | `docs/architecture-cible.md` |
| Intégrer le lookup de zones | `docs/plan-zone-lookup-seed.md` |
| Workflow d'équipe (branches, PR, board) | `docs/workflow-equipe.md` |
