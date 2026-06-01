# .github/workflows/

Workflows GitHub Actions (CI/CD) — chantier de **Romain**.

- `pipeline.yml` — orchestration : setup infra → ingestion → `dbt build` (à venir).
- `release.yml` — publication sur tag `v*` (à venir, niveau 2).

> S'appuie sur les **contrats d'interface** (cf. `docs/kickoff-equipe.md` §3), donc développable
> en parallèle. Auth Snowflake par **clé RSA** via secrets repo (jamais de clé en clair).
