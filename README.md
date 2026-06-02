# 🚕 NYC Taxi Data Pipeline — Équipe *Irregular Croppers*

Projet de groupe (Simplon Data Engineer) : pipeline de données de bout en bout sur les
**NYC Yellow Taxi Trip Records** — ingestion → nettoyage → transformation (**dbt**) → analyse,
le tout dans **Snowflake** et orchestré par **GitHub Actions**.

> 🚧 Repo en cours de construction. On démarre par le cadrage ; les briques techniques
> (setup Snowflake, ingestion, dbt, CI) arriveront **une par une, via Pull Request**.

## Par où commencer
- 🚀 **Nouveau ? → [docs/onboarding.md](docs/onboarding.md)** — du clone au `dbt build` (connexion Snowflake, infra, seed de dev).
- 📋 **[docs/brief.md](docs/brief.md)** — le sujet et les livrables attendus.
- 🤝 Organisation d'équipe : **[docs/workflow-equipe.md](docs/workflow-equipe.md)** · **[docs/guide-github-projects.md](docs/guide-github-projects.md)**.

## Comment contribuer
1. `git checkout main && git pull`
2. `git checkout -b feat/ma-tache` (une branche par tâche)
3. Coder, tester, puis `git push -u origin feat/ma-tache`
4. Ouvrir une **Pull Request** → review d'un coéquipier → merge sur `main`.

> Règles : `main` protégée (pas de push direct), **jamais de secret/clé/donnée** dans Git.

## Stack
Snowflake · dbt Core · GitHub Actions · Python (uv, Polars)
