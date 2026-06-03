# scripts/

Scripts Python / shell du projet.

- `ingest.sh` — Pipeline complet d'ingestion : téléchargement des fichiers Parquet locaux, chargement (PUT) dans le Stage Snowflake, et injection (COPY INTO) dans la table `RAW`.
- `explore_data.py` — Exploration des données / EDA (à venir, brique J1).

> **Contrat d'interface :** L'ingestion s'exécute depuis la racine du projet via :
> ```bash
> ./scripts/ingest.sh [--annees <annees>] [--force]
> ```

---

## Configuration requise pour `ingest.sh`

Le script utilise le CLI Snowflake (`snow`) via le profil de connexion nommé `projet7`. Pour qu'il fonctionne, vous devez configurer vos identifiants dans un fichier de configuration global sur votre machine (et non dans le répertoire du projet).

### 1. Fichier de configuration global (`config.toml`)

Vous devez créer ou modifier le fichier TOML situé à la racine de votre dossier utilisateur :
👉 **Chemin :** `~/.snowflake/config.toml` *(ex: `/Users/votre_nom/.snowflake/config.toml`)*

Ajoutez-y la configuration suivante en remplaçant par vos identifiants de connexion **Snowsight** :

```toml
[connections.projet7]
account = "VOTRE_ORGANISATION-VOTRE_COMPTE"  # Attention : remplacer le point (.) par un tiret (-)
user = "VOTRE_NOM_D_UTILISATEUR"
password = "VOTRE_MOT_DE_PASSE"
role = "ACCOUNTADMIN"
warehouse = "NYC_TAXI_WH"
database = "NYC_TAXI_DB"
schema = "RAW"