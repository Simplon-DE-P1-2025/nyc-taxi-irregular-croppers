# Workflow d'équipe au quotidien

> Comment on travaille concrètement : 4 comptes Snowflake **isolés** + **1 repo GitHub partagé**
> (dans l'orga de l'école) + **1 CI** qui tourne sur **un compte de référence**.

## Vue d'ensemble
```
   Chacun code en local                 GitHub (orga école)              Snowflake
   sur SON compte Snowflake             repo partagé + PR                (1 compte/personne)
   ┌─────────────────────┐    push     ┌──────────────────┐
   │ Romain  (compte R)  │ ─────────►  │  branche feat/…  │
   │ Alice   (compte A)  │ ─PR+review► │      main        │
   │ Karim   (compte K)  │             └────────┬─────────┘
   │ Sofia   (compte S)  │                      │ merge sur main / dispatch
   └─────────────────────┘                      ▼
                                        GitHub Actions (CI)
                                        secrets = compte de RÉFÉRENCE (ex. Romain)
                                                  │
                                                  ▼  setup + ingestion + dbt build
                                        ❄️  écrit dans le compte Snowflake de référence
                                            = base de la démo / soutenance
```
**Idée clé** : le code est partagé (Git), les données ne le sont pas. Chacun valide chez lui ;
la CI fait foi sur **un** compte commun (la « prod » du projet).

## 1. Setup unique (chaque membre, une fois) — cf. `setup-snowflake.md`
1. Crée son compte Snowflake + sa clé RSA + sa connexion `snow projet7`.
2. `git clone <repo>` → `uv sync`.
3. `snow sql -c projet7 -f snowflake/01_setup_infra.sql` (crée l'infra sur SON compte).
4. Configure dbt (`profiles.yml` via env vars) → `cd dbt_nyc_taxi && uv run dbt debug`.

## 2. Boucle de dev quotidienne (chacun)
```bash
git checkout main && git pull            # repartir à jour
git checkout -b feat/staging-nettoyage   # 1 branche par tâche

# … coder (modèles dbt, scripts…) et TESTER EN LOCAL sur son compte :
cd dbt_nyc_taxi && uv run dbt build --select staging   # ou dbt run/test ciblé

git add -A && git commit -m "feat: filtres de nettoyage staging"
git push -u origin feat/staging-nettoyage
# → ouvrir une Pull Request sur GitHub, demander une review
```
- Un **coéquipier review** la PR, puis **merge sur `main`** (branche protégée → pas de push direct).
- Au merge, la **CI** se déclenche et rejoue tout le pipeline sur le **compte de référence**.

## 3. La CI concrètement (compte de référence = ex. Romain)
**Où** : `.github/workflows/pipeline.yml`. **Sur quel compte** : celui dont les secrets sont dans le repo.

**Secrets à créer une seule fois** (Settings → Secrets and variables → Actions) :
| Secret | Valeur |
|---|---|
| `SNOWFLAKE_ACCOUNT` | l'account identifier du compte de réf. (ex. `TPWBVCJ-YT98088`) |
| `SNOWFLAKE_USER` | le user (ex. `5AMCHAKA`) |
| `SNOWFLAKE_PRIVATE_KEY` | le **contenu** du fichier `.p8` (clé privée, multi-lignes) |

**Ce que la CI fait à chaque exécution** (sur push `main`, PR, ou bouton « Run workflow ») :
1. Installe uv + dépendances.
2. Reconstitue la clé privée depuis le secret → configure la connexion `snow`.
3. `01_setup_infra.sql` (idempotent) → `ingest.sh` → `dbt deps` + `dbt build`.
4. Archive les artefacts dbt (manifest, run_results).

→ Résultat : le compte de référence contient toujours un pipeline **à jour et démontrable**.
Les 3 autres valident en local sur leur propre compte avant de pousser.

### Sécurité de la clé en CI
- Les secrets **ne sont pas lisibles** dans l'UI ni les logs (masqués).
- Mais toute personne avec accès **write** au repo peut modifier le workflow → limiter les
  collaborateurs aux 4 (+ formateur).
- *(Bonus propre)* : plutôt que la clé ACCOUNTADMIN, créer un **user Snowflake dédié `CI_USER`**
  avec un rôle restreint (accès `NYC_TAXI_DB` + `NYC_TAXI_WH`) et SA propre clé pour la CI.

## 4. Règles d'or
- `main` **protégée** : tout passe par PR + 1 review.
- **Jamais** de secret/clé/donnée dans Git (`.gitignore` les bloque).
- 1 branche = 1 tâche ; commits clairs (`feat:`, `fix:`, `docs:`).
- Tester **en local** avant de pousser ; la CI confirme sur le compte de référence.
- Kanban GitHub Projects tenu à jour ; point quotidien 15 min.
