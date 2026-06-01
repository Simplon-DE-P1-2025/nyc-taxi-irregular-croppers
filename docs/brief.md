# Brief — Projet 7 : Pipeline de données NYC Taxi

> **Rôle** : Data Engineer · **Thème** : Snowflake + dbt + supervision et maintenance d'application
> **Cadre** : projet en groupe · **3 jours** · sprints journaliers (ingestion / nettoyage / analyse)
>
> Ce document est le point d'entrée. Détail technique → `architecture-cible.md` · monitoring → `monitoring-snowflake.md`.

---

## 1. Objectif
Construire une architecture de **Data Warehouse moderne** de bout en bout à partir des données
publiques **NYC Taxi Trip Data** : ingestion → nettoyage → transformation → documentation → analyse,
en garantissant la **qualité des données** et la **scalabilité**, avec un pipeline **automatisé et orchestré**.

## 2. Dataset
| | |
|---|---|
| Source | NYC Taxi & Limousine Commission (**Yellow** taxi) |
| Volume | **~40 millions de trajets** |
| Période | **2024 + début 2025** (≥ 12 mois) |
| Format | fichiers **Parquet mensuels** |
| Pattern | `yellow_tripdata_YYYY-MM.parquet` |
| URL source | `https://d37ci6vzurychx.cloudfront.net/trip-data/` |

## 3. Compétences visées
- Ingestion de données depuis des sources externes
- Architecture Data Warehouse en couches **RAW → STAGING → FINAL**
- Nettoyage et transformation de données
- Documentation et tests qualité
- Orchestration de pipelines

## 4. Architecture imposée (résumé)
`RAW` (brut) → `STAGING` (nettoyé + métriques) → `FINAL` (tables analytiques).
Objets exacts à créer : warehouse **`NYC_TAXI_WH`**, base **`NYC_TAXI_DB`**, schémas **`RAW` / `STAGING` / `FINAL`**,
table **`RAW.yellow_taxi_trips`**, tables **`FINAL.daily_summary` / `zone_analysis` / `hourly_patterns`**.
→ DDL, règles de nettoyage, métriques et SQL complets dans **`docs/architecture-cible.md`**.

## 5. Étapes imposées
1. Configuration Snowflake (warehouse, base, schémas)
2. Chargement des données 2024-2025 (Parquet → `RAW`)
3. Analyse et nettoyage des données
4. Transformations de base dans Snowflake (SQL)
5. Transformation avec **dbt Core**
6. **Orchestration avec GitHub Actions** (OBLIGATOIRE)

### Découpage en sprints (3 jours)
- **J1 — Ingestion** : config Snowflake + chargement RAW
- **J2 — Nettoyage** : analyse qualité + `STAGING.clean_trips`
- **J3 — Analyse** : tables `FINAL` + KPIs + rapport

## 6. Modalités pédagogiques
- Projet **en groupe**.
- Outils : GitHub (versioning), VS Code, Snowflake Web UI.
- Suivi via **Kanban** (GitHub Projects / Notion / Trello).
- Versionner avec Git, documenter chaque étape, tester régulièrement, optimiser les coûts (Auto-Suspend).

## 7. Livrables
| Livrable | Statut |
|---|---|
| Architecture Snowflake complète (warehouse, base, 3 schémas) | **Obligatoire** |
| Scripts SQL / dbt (transformations + calculs de métriques) | **Obligatoire** |
| Rapport d'analyse (qualité des données + KPIs calculés) | **Obligatoire** |
| Pipeline automatisé & orchestré (GitHub Actions) | **Obligatoire** |
| README documenté + documentation technique + support de soutenance | **Obligatoire** |
| Dashboard de visualisation (Streamlit / Tableau / Power BI) | *Optionnel* |
| Dashboard de monitoring (Snowflake worksheet ou Grafana) | *Optionnel* — voir `monitoring-snowflake.md` |

## 8. KPIs minimum attendus
Nb de trajets mensuels · revenu moyen par trajet · distance moyenne · top 10 zones de pickup · heures de pointe.

## 9. Critères d'évaluation
- Évaluation **continue** : qualité du code, rigueur de la structure Snowflake, collaboration, nettoyage.
- Architecture respectée, code fonctionnel, documentation claire, automatisation/optimisation.
- **Soutenance finale** : support de présentation + démonstration.

## 10. Points à clarifier / d'attention
- ❓ **API d'exploitation** : mentionnée dans un des documents (« exploitation via une API ») mais
  **absente de la consigne canonique** (qui parle de dashboard). → à confirmer avec le formateur.
- ⚠️ 6 pièges techniques repérés (external stage S3, auth CI key-pair, version dbt, test relationships,
  coûts MEDIUM…) → détaillés dans **`docs/architecture-cible.md`**.

## 11. Liens de référence
- Consigne canonique : https://github.com/gsoulat/formation-data-engineer/blob/main/99-Brief/Snowflake+Dbt/nyc_taxi_dbt_pipeline.md
- Ressources Snowflake : https://github.com/gsoulat/formation-data-engineer/tree/main/04-Cloud-Platforms/snowflake
- Ressources dbt Core & cheatsheet : https://github.com/gsoulat/formation-data-engineer/tree/main/06-Data-Engineering/Dbt
- Monitoring Snowflake (support) : https://github.com/gsoulat/formation-data-engineer/blob/main/04-Cloud-Platforms/snowflake/09-monitoring.md
- Intégration Grafana-Snowflake : https://www.flexera.com/blog/finops/grafana-snowflake-integration
- Dataset Simplon : https://simplonline.co/trainer-workspace/briefs/6793d8a2-8f57-4a80-af9a-90148f0bf34a
- Réf. dbt + Snowflake (Medium) : https://dipikajiandani.medium.com/dbt-snowflake-2831681b67f9
- Cheatsheet dbt (xlsx) : https://simplonline-v3-prod.s3.eu-west-3.amazonaws.com/media/file/xlsx/aide-memoire-dbt-nyc-taxi-6a1ceec00f09d147952284.xlsx
