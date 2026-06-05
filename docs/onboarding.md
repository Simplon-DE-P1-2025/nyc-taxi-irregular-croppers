# Onboarding — du clone au `dbt build`

Process pour qu'un nouveau membre soit opérationnel en local. **Comptes isolés (1/personne)** :
la connexion `snow` s'appelle **`projet7` pour tout le monde**, mais chacun la fait pointer vers
**son** compte. C'est ce qui fait tourner le même code à l'identique chez les 4.

## Prérequis
- Compte Snowflake trial (**AWS / eu-west-1 / Standard**, cf. `kickoff-equipe.md`).
- [`uv`](https://docs.astral.sh/uv/) et la **Snowflake CLI** (`snow`) installés.
- `openssl` (pour générer la clé RSA, étape 3).

> 💡 **Pas besoin d'installer Python toi-même.** `uv sync` télécharge et gère sa propre
> version de Python (3.12, cf. `.python-version`). Le projet est configuré en
> `python-preference = "only-managed"` : uv **ignore** volontairement un éventuel
> `pyenv`/`conda` local — ces Python compilés à la main sont souvent incomplets
> (modules `_bz2`, `_lzma`, `_sqlite3` manquants → `dbt` plante au démarrage).
>
> ⚠️ **Désactive tout environnement actif avant de commencer** (`conda deactivate`,
> ou `deactivate` si un `venv` est activé). Sinon tu verras un avertissement
> `VIRTUAL_ENV … does not match the project environment` : uv l'ignore, mais autant
> partir propre.
>
> 🐧 **Sous WSL : clone le repo côté Linux (`~/...`), pas sous `/mnt/c/...`.** Sur un
> disque Windows monté, `uv` ne peut pas faire de hardlink (install lente, copie
> intégrale) — `~/projets/nyc-taxi-irregular-croppers` est bien plus rapide.

> **Auth = paire de clés RSA** (`snowflake_jwt`), pour le dev local **et** la CI.
> ⚠️ N'utilise **pas** `externalbrowser` : c'est du SSO fédéré (SAML) qui exige un fournisseur
> d'identité (Okta, Azure AD…) configuré sur le compte. Nos comptes trial isolés n'en ont pas →
> `externalbrowser` renvoie une **erreur SAML**. La clé RSA est la seule méthode qui marche ici.

## Étapes

```bash
# 1) Cloner
git clone https://github.com/Simplon-DE-P1-2025/nyc-taxi-irregular-croppers
cd nyc-taxi-irregular-croppers

# 2) Environnement Python (dépendances verrouillées)
uv sync

# 3) Générer SA clé RSA + créer SA connexion snow (nom imposé : projet7 ; compte = le sien)
#
#  a) Générer la paire de clés (clé privée .p8 + clé publique .pub) :
mkdir -p ~/.snowflake
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/nyc_taxi_key.p8 -nocrypt
openssl rsa -in ~/.snowflake/nyc_taxi_key.p8 -pubout -out ~/.snowflake/nyc_taxi_key.pub
chmod 600 ~/.snowflake/nyc_taxi_key.p8
#  → la clé publique SUR UNE LIGNE (à coller dans Snowsight à l'étape b) :
grep -v "PUBLIC KEY" ~/.snowflake/nyc_taxi_key.pub | tr -d '\n'; echo

#  b) Poser la clé publique sur ton user : dans Snowsight (https://app.snowflake.com),
#     ouvre un Worksheet en rôle ACCOUNTADMIN et exécute (garde les guillemets autour du user,
#     surtout s'il commence par un chiffre, ex. "7JDUPONT") :
#        SELECT CURRENT_USER();                                    -- ton user EXACT
#        ALTER USER "<SON_USER>" SET RSA_PUBLIC_KEY='<CLE_PUBLIQUE_UNE_LIGNE>';

#  c) Créer la connexion (account = le sien ; cf. « Où trouver tes infos » plus bas) :
snow connection add \
  --connection-name projet7 \
  --account <SON_ORG-SON_ACCOUNT> \
  --user <SON_USER> \
  --authenticator SNOWFLAKE_JWT \
  --private-key "$HOME/.snowflake/nyc_taxi_key.p8" \
  --warehouse NYC_TAXI_WH \
  --database NYC_TAXI_DB \
  --role ACCOUNTADMIN \
  --no-interactive
snow connection test -c projet7
#  ⏳ « JWT token is invalid » juste après la pose de la clé = propagation (1-2 min), réessaie.
#  ⚠️ « warehouse does not exist » = normal tant que l'étape 4 n'est pas faite : l'AUTH, elle, marche.

# 4) Créer SON infra (idempotent) + données de dev
snow sql -c projet7 -f snowflake/01_setup_infra.sql
snow sql -c projet7 -f snowflake/seed_dev_sample.sql

# 5) dbt : SON profil de dev, puis build
mkdir -p ~/.dbt && cp profiles.yml.example ~/.dbt/profiles.yml
#   → le profil lit 3 variables d'env (compte = le sien) : exporte-les avant dbt
export SNOWFLAKE_ACCOUNT="<SON_ORG-SON_ACCOUNT>"          # cf. tableau ci-dessous
export SNOWFLAKE_USER="<SON_USER>"
export SNOWFLAKE_PRIVATE_KEY_PATH="$HOME/.snowflake/nyc_taxi_key.p8"
cd dbt_nyc_taxi
uv run dbt deps
uv run dbt build       # construit staging → marts sur SON compte, contre le seed
```

## Où trouver tes infos (étape 3)
Dans **Snowsight** (l'interface web Snowflake), une fois connecté à ton compte :

| À renseigner | Où le trouver |
|---|---|
| `<SON_ORG-SON_ACCOUNT>` (`--account`) | Bas-gauche → clic sur ton **nom de compte** → **View account details** → champ **Account / Account Identifier**, format `ORGNAME-ACCOUNTNAME` (ex. `ABCDEFG-AB12345`). |
| `<SON_USER>` (`--user`) | Ton **nom d'utilisateur** Snowflake (bas-gauche → ton profil), **pas** ton email. |
| `--role` / `--warehouse` / `--database` | Déjà fixés par convention : `ACCOUNTADMIN` / `NYC_TAXI_WH` / `NYC_TAXI_DB` (ces deux derniers sont créés par `01_setup_infra.sql` à l'étape 4). |

> ⚠️ `--account` n'est **pas** un mot libre (ni `simplon`, ni le nom du repo) : c'est l'**identifiant exact**
> `ORGNAME-ACCOUNTNAME`. Une faute ici = `snow connection test` qui échoue.

## Bon à savoir
- **`projet7`** = même *nom* pour tous, branché sur **son** compte (comptes isolés → pas de collision).
- **Clé RSA = standard partout** : même méthode (`snowflake_jwt`) en local et en CI. `externalbrowser`
  (SSO/SAML) **ne fonctionne pas** sur nos comptes trial isolés (pas de fournisseur d'identité →
  erreur SAML). La clé reste sur ta machine (`~/.snowflake/`, jamais committée).
- **`seed_dev_sample.sql`** = fixture de dev (~15 lignes) pour développer dbt **sans attendre l'ingestion réelle**
  (issue #4). **DEV ONLY** (il fait un `TRUNCATE`).
- **Modèles dbt** : la chaîne complète est implémentée (staging → `int_trip_metrics` →
  3 marts + seed `taxi_zone_lookup`) — un `dbt build` exécute 1 seed + 5 modèles + 41 tests.
- **`ModuleNotFoundError: No module named '_bz2'`** (ou `_lzma`, `_sqlite3`) au lancement de
  `dbt` = ton `.venv` a été créé avec un Python `pyenv`/`conda` incomplet. Repars propre depuis
  la **racine** du projet : `uv python install 3.12 && rm -rf .venv && uv sync`. La config
  `python-preference = "only-managed"` (pyproject) force désormais un Python uv complet.

## Workflow d'équipe
Branches + PR (`main` protégée), Kanban GitHub Projects, `Closes #N` dans les PR.
Détails : `workflow-equipe.md` et `guide-github-projects.md`.
