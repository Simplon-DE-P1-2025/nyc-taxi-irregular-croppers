#!/bin/bash

# Configuration stricte de Bash pour la robustesse :
# -E : permet aux fonctions et sous-shells d'heriter du piege (trap) ERR
# -e : arrete le script immediatement si une commande echoue
# -u : considere les variables non definies comme des erreurs
# -o pipefail : renvoie le code d'erreur d'un pipeline si un element echoue
set -Eeuo pipefail

# Intercepte les erreurs (ERR) et execute la fonction de diagnostic
trap 'handler_erreur $? $LINENO' ERR

handler_erreur() {
    local code_erreur=$1
    local ligne_erreur=$2
    echo ""
    echo "============================================================"
    echo "CRITICAL ERROR : LE PIPELINE A ECHOUE"
    echo "============================================================"
    echo "Statut de l'erreur : $code_erreur"
    echo "Ligne du script    : $ligne_erreur"
    echo "Derniere commande  : $BASH_COMMAND"
    echo "============================================================"
    echo "Statut : Ingestion interrompue. Verifiez les logs ci-dessus."
    echo "============================================================"
    exit "$code_erreur"
}

# Recupere le dossier ou se trouve ce script et se repositionne a la racine du projet
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Configuration de la connexion Snowflake CLI
CONNEXION_SNOWFLAKE="projet7"

echo "============================================================"
echo "DEMARRAGE DU PIPELINE D'INGESTION NYC TAXI"
echo "============================================================"

# --- ETAPE 1 : Telechargement des donnees ---
echo "Etape 1 : Telechargement des fichiers Parquet..."
python3 scripts/download_data.py "$@"

echo ""
echo "------------------------------------------------------------"

# --- ETAPE 2 : Envoi des fichiers sur le Stage Snowflake ---
# Le PUT ne tourne que s'il y a des parquet locaux : si la TLC est
# indisponible (403/404 passager), le stage Snowflake fait foi et le
# COPY de l'etape 3 reste idempotent — le pipeline ne depend plus du
# reseau TLC pour les fichiers deja stages.
echo "Etape 2 : Chargement des fichiers (PUT) dans le Stage Snowflake..."
shopt -s nullglob
fichiers_parquet=(data/raw/*.parquet)
shopt -u nullglob
if [ ${#fichiers_parquet[@]} -eq 0 ]; then
    echo "Aucun parquet local (TLC indisponible ?) : PUT saute, le stage existant fait foi."
else
    snow sql -c $CONNEXION_SNOWFLAKE -q "
      USE DATABASE NYC_TAXI_DB;
      USE SCHEMA RAW;
      PUT file://data/raw/*.parquet @NYC_TAXI_DB.RAW.nyc_taxi_stage AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
    "
fi

echo "------------------------------------------------------------"

# --- ETAPE 3 : Injection dans la table RAW ---
echo "Etape 3 : Chargement des donnees (COPY INTO)..."
snow sql -c $CONNEXION_SNOWFLAKE -q "
  USE DATABASE NYC_TAXI_DB;
  USE SCHEMA RAW;
  USE WAREHOUSE NYC_TAXI_WH;

  COPY INTO NYC_TAXI_DB.RAW.yellow_taxi_trips
  FROM @NYC_TAXI_DB.RAW.nyc_taxi_stage
  FILE_FORMAT = (TYPE = PARQUET, USE_LOGICAL_TYPE =
  TRUE)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  INCLUDE_METADATA = (loaded_at = METADATA\$START_SCAN_TIME, source_file = METADATA\$FILENAME)
  PURGE = FALSE;
"

echo "============================================================"
echo "INGESTION TERMINEE AVEC SUCCES"
echo "============================================================"