# Kickoff équipe — Projet NYC Taxi

> À lire avant de coder. Objectif : se mettre d'accord sur **la façon de travailler** et acter les
> **décisions communes**. Équipe de 4, **3 jours**.

---

## 1. Le projet
Pipeline de données de bout en bout sur les **NYC Yellow Taxi Trip Records** (~40 M trajets, 2024 + début 2025,
fichiers Parquet) : **ingestion → nettoyage → transformation (dbt) → analyse/KPIs**, dans **Snowflake**,
orchestré par **GitHub Actions**. Architecture imposée : `RAW → STAGING → FINAL`.
Détails : `docs/brief.md`.

## 2. Comment on s'organise
- **Comptes Snowflake : 1 par personne** (imposé), **isolés** entre eux. La cohérence de l'équipe ne
  vient donc **pas** des données mais du **code partagé** (ce repo), que chacun rejoue sur son compte.
- **Repo GitHub partagé** (orga école, public) = notre source de vérité.
- **Rythme** : sprints journaliers — **J1** ingestion + exploration · **J2** nettoyage · **J3** analyse/KPIs.
  Point d'équipe **15 min chaque matin**.

## 3. Contrats d'interface (la clé pour bosser en parallèle)
Pour avancer chacun de son côté sans se bloquer, on **fige dès le départ** les noms de fichiers et
les commandes que tout le monde utilisera. Tant que chacun les respecte, les briques s'emboîtent.

| Contrat | Rôle |
|---|---|
| `snowflake/01_setup_infra.sql` | crée l'infra (warehouse `NYC_TAXI_WH`, base `NYC_TAXI_DB`, schémas `RAW`/`STAGING`/`FINAL`) |
| `scripts/ingest.sh <mois…>` | charge les Parquet dans `RAW` |
| `cd dbt_nyc_taxi && dbt build` | exécute les transformations + tests |

➡️ Grâce à ça, la **CI peut être développée en parallèle** des autres briques (elle appelle ces
commandes, peu importe qui écrit leur contenu).

## 4. Répartition des rôles
- **Romain → CI/CD GitHub Actions + releases.** Peut démarrer **tout de suite** : il construit le
  workflow contre les contrats du §3 et le teste sur son compte, sans attendre les autres.
- **Les 3 autres :**
  - **J1 — Exploration des données (EDA)** : *travail d'équipe et livrable noté* (rapport qualité).
    Chacun manipule les données : valeurs manquantes, anomalies, distributions, **et vérification du
    schéma réel des Parquet** (ne pas supposer qu'il colle au brief).
  - puis **ingestion**, **nettoyage** (dbt `staging`), **analyse** (dbt `marts` + KPIs + rapport).
- *Documentation + support de soutenance : transverse, tout le monde.*
> Modèle à ajuster en réunion (par couche, ou en binômes par sprint).

## 5. Workflow Git
- **`main` protégée** : pas de push direct, tout passe par **Pull Request + 1 review**.
- **1 branche par tâche** : `feat/…`, `fix/…`.
- Suivi via **GitHub Projects** (issues = cartes) — cf. `docs/guide-github-projects.md`.
- **Jamais** de secret / clé / donnée dans Git (`.gitignore` les bloque).
- Détail du flux quotidien : `docs/workflow-equipe.md`.

## 6. Versioning & releases
- **SemVer** : `0.x` pendant le dev, **`1.0.0`** pour la soutenance.
- Un **tag par fin de sprint** : `v0.1.0` (fin J1) → `v0.2.0` (J2) → `v0.3.0` (J3) → `v1.0.0` (soutenance).
- L'automatisation (release sur tag) fait partie du chantier CI (Romain).

## 7. Décisions à acter en réunion
| # | Décision | Piste |
|---|---|---|
| 1 | Paramètres de compte Snowflake | édition Standard ; région **sans importance** (comptes isolés) |
| 2 | Mois de données chargés en dev | ex. 3 mois (économie de crédits) ; année complète au run final |
| 3 | **Contrats d'interface** du §3 | les figer maintenant |
| 4 | Compte de référence pour la CI | 1 seul jeu de secrets repo → à désigner |
| 5 | Répartition fine des rôles | cf. §4 |
| 6 | Schéma de dev dbt par personne | `dbt_<prenom>` |
| 7 | Outil de qualité de données | dbt tests |
| 8 | Qui crée le repo + le board Projects | **Romain** |
| 9 | Conventions branches/commits | `feat/ fix/` + commits clairs |

## 8. Prochaines étapes
1. Chacun crée **son compte Snowflake + sa clé** (`docs/setup-snowflake.md`).
2. On crée le **repo partagé** + le **board GitHub Projects**.
3. On **fige les contrats** du §3 et on se répartit les rôles.
4. On lance : **EDA** (équipe) et **CI** (Romain) **en parallèle**.
