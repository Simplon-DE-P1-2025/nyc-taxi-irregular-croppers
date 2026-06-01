# dbt_nyc_taxi/

Projet **dbt Core** : transformations `RAW → STAGING → FINAL`.

Structure cible (construite par PR au fil des sprints) :
```
models/
  staging/        # nettoyage (vues)
  intermediate/   # métriques / enrichissement
  marts/          # tables analytiques + KPIs (FINAL)
```

> Contrat d'interface : les transformations s'exécutent via `cd dbt_nyc_taxi && dbt build`.
> Chacun configure son `profiles.yml` (clé RSA) — cf. `docs/setup-snowflake.md`. Jamais commité.
