# Onboarding — du clone au `dbt build`

Process pour qu'un nouveau membre soit opérationnel en local. **Comptes isolés (1/personne)** :
la connexion `snow` s'appelle **`projet7` pour tout le monde**, mais chacun la fait pointer vers
**son** compte. C'est ce qui fait tourner le même code à l'identique chez les 4.

## Prérequis
- Compte Snowflake trial (**AWS / eu-west-1 / Standard**, cf. `kickoff-equipe.md`), MFA activée.
- [`uv`](https://docs.astral.sh/uv/) et la **Snowflake CLI** (`snow`) installés.

## Étapes

```bash
# 1) Cloner
git clone https://github.com/Simplon-DE-P1-2025/nyc-taxi-irregular-croppers
cd nyc-taxi-irregular-croppers

# 2) Environnement Python (dépendances verrouillées)
uv sync

# 3) Créer SA connexion snow (nom imposé : projet7 ; compte = le sien)
#    En local, auth navigateur (MFA) = le plus simple, pas de clé RSA à gérer.
#    ⚠️ Aux invites « Enter password / host / port / region / private key… » → laisser VIDE (Entrée) :
#       avec externalbrowser, seuls account + user comptent. Voir « Où trouver tes infos » plus bas.
snow connection add \
  --connection-name projet7 \
  --account <SON_ORG-SON_ACCOUNT> \
  --user <SON_USER> \
  --authenticator externalbrowser \
  --warehouse NYC_TAXI_WH \
  --database NYC_TAXI_DB \
  --role ACCOUNTADMIN
snow connection test -c projet7          # ouvre le navigateur pour le login MFA

# 4) Créer SON infra (idempotent) + données de dev
snow sql -c projet7 -f snowflake/01_setup_infra.sql
snow sql -c projet7 -f snowflake/seed_dev_sample.sql

# 5) dbt : SON profil de dev, puis build
mkdir -p ~/.dbt && cp profiles.yml.example ~/.dbt/profiles.yml
#   → éditer ~/.dbt/profiles.yml : remplacer <TON_ORG-TON_ACCOUNT> et <TON_USER> (cf. tableau ci-dessous).
#     Déjà en externalbrowser : aucun mot de passe / clé / variable d'env à gérer.
cd dbt_nyc_taxi
uv run dbt deps
uv run dbt build       # construit staging → marts sur SON compte, contre le seed
```

## Où trouver tes infos (étape 3)
Dans **Snowsight** (l'interface web Snowflake), une fois connecté à ton compte :

| À renseigner | Où le trouver |
|---|---|
| `<SON_ORG-SON_ACCOUNT>` (`--account`) | Bas-gauche → clic sur ton **nom de compte** → **View account details** → champ **Account / Account Identifier**, format `ORGNAME-ACCOUNTNAME` (ex. `TPWBVCJ-YT98088`). |
| `<SON_USER>` (`--user`) | Ton **nom d'utilisateur** Snowflake (bas-gauche → ton profil), **pas** ton email. |
| `--role` / `--warehouse` / `--database` | Déjà fixés par convention : `ACCOUNTADMIN` / `NYC_TAXI_WH` / `NYC_TAXI_DB` (ces deux derniers sont créés par `01_setup_infra.sql` à l'étape 4). |

> ⚠️ `--account` n'est **pas** un mot libre (ni `simplon`, ni le nom du repo) : c'est l'**identifiant exact**
> `ORGNAME-ACCOUNTNAME`. Une faute ici = `snow connection test` qui échoue.

## Bon à savoir
- **`projet7`** = même *nom* pour tous, branché sur **son** compte (comptes isolés → pas de collision).
- **RSA vs navigateur** : `externalbrowser` (MFA) suffit en local. La **clé RSA** ne sert qu'à la **CI**
  (login headless, sur le compte de référence) — inutile de la générer pour du dev local.
- **`seed_dev_sample.sql`** = fixture de dev (~15 lignes) pour développer dbt **sans attendre l'ingestion réelle**
  (issue #4). **DEV ONLY** (il fait un `TRUNCATE`).
- **Modèles dbt** : tant que #13-16 ne sont pas implémentés, ce sont des stubs (`select 1`) →
  le `dbt build` valide la *chaîne*, pas encore la logique métier.

## Workflow d'équipe
Branches + PR (`main` protégée), Kanban GitHub Projects, `Closes #N` dans les PR.
Détails : `workflow-equipe.md` et `guide-github-projects.md`.
