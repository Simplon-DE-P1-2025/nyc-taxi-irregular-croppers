# .github/workflows/

Workflows GitHub Actions (CI/CD) — chantier de **Romain**.

- `ci.yml` — **CI légère sur chaque PR vers `main`** : lint Python (ruff) + `dbt parse` hors-ligne
  (profil factice `dbt_nyc_taxi/ci/profiles.yml`). Gratuit, rapide, **aucun secret Snowflake**.
- `pipeline.yml` — orchestration : setup infra → ingestion → `dbt build` (à venir).
- `release.yml` — publication sur tag `v*` (à venir, niveau 2).

## Rendre la CI obligatoire (required status check)

Pour bloquer le merge tant que `ci.yml` n'est pas vert (point optionnel de #17) :
`Settings → Branches → Add branch ruleset` (ou *Branch protection rule*) sur `main` →
cocher **Require status checks to pass** → sélectionner le check **`validate`**
(le nom du job de `ci.yml`). Nécessite les droits admin du dépôt.

> S'appuie sur les **contrats d'interface** (cf. `docs/kickoff-equipe.md` §3), donc développable
> en parallèle. Auth Snowflake par **clé RSA** via secrets repo (jamais de clé en clair).
