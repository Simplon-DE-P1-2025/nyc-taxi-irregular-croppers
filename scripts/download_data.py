"""
================================================================================
 download_data.py — Telechargement des fichiers Parquet NYC TLC (yellow taxi)
 Projet NYC Taxi. A executer depuis la racine du projet :
 
     python scripts/download_data.py                 # saute les fichiers existants
     python scripts/download_data.py --force          # retelecharge tout
     python scripts/download_data.py --annees 2025    # une seule annee
 
 Telecharge dans data/raw/ (dossier ignore par Git, regenerable a la demande).
 La donnee TLC est figee une fois publiee : on saute par defaut ce qui existe.
================================================================================
"""
 
import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path
 
# --- Configuration -----------------------------------------------------------
BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
DOSSIER_SORTIE = Path("data/raw")
TYPE_TAXI = "yellow"
ANNEES_DEFAUT = [2024, 2025]
MOIS = range(1, 13)
 
 
def barre_progression(bloc_recu, taille_bloc, taille_totale):
    """Affiche une barre de progression pendant le telechargement d'un fichier."""
    if taille_totale <= 0:
        return
    telecharge = bloc_recu * taille_bloc
    pourcent = min(100, telecharge * 100 // taille_totale)
    barres = pourcent // 4
    affichage = "#" * barres + "-" * (25 - barres)
    mo = telecharge / (1024 * 1024)
    mo_total = taille_totale / (1024 * 1024)
    sys.stdout.write(f"\r    [{affichage}] {pourcent:3d}%  ({mo:.1f}/{mo_total:.1f} Mo)")
    sys.stdout.flush()
 
 
def telecharger_fichier(annee, mois, force):
    """Telecharge un fichier mensuel. Retourne 'ok', 'saute' ou 'absent'."""
    nom_fichier = f"{TYPE_TAXI}_tripdata_{annee}-{mois:02d}.parquet"
    url = f"{BASE_URL}/{nom_fichier}"
    chemin_local = DOSSIER_SORTIE / nom_fichier
 
    if chemin_local.exists() and not force:
        print(f"  Deja present, ignore : {nom_fichier}")
        return "saute"
 
    try:
        print(f"  Telechargement de {nom_fichier}")
        urllib.request.urlretrieve(url, chemin_local, reporthook=barre_progression)
        print()  # saut de ligne apres la barre de progression
        return "ok"
    except urllib.error.HTTPError as e:
        # Un mois non encore publie renvoie 403 ou 404 : on signale et on continue.
        print(f"\r    Indisponible (erreur {e.code}) : {nom_fichier}{' ' * 30}")
        # On supprime le fichier vide eventuellement cree par urlretrieve.
        if chemin_local.exists() and chemin_local.stat().st_size == 0:
            chemin_local.unlink()
        return "absent"
 
 
def main():
    parser = argparse.ArgumentParser(
        description="Telecharge les fichiers Parquet NYC TLC (yellow taxi)."
    )
    parser.add_argument(
        "--annees",
        type=int,
        nargs="+",
        default=ANNEES_DEFAUT,
        help="Annees a telecharger (defaut : 2024 2025).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retelecharge meme les fichiers deja presents.",
    )
    args = parser.parse_args()
 
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
 
    print(f"Dossier de sortie : {DOSSIER_SORTIE.resolve()}")
    print(f"Annees ciblees    : {args.annees}")
    print(f"Mode force        : {'oui' if args.force else 'non'}")
    print("-" * 60)
 
    compteurs = {"ok": 0, "saute": 0, "absent": 0}
 
    for annee in args.annees:
        print(f"Annee {annee}")
        for mois in MOIS:
            resultat = telecharger_fichier(annee, mois, args.force)
            compteurs[resultat] += 1
 
    print("-" * 60)
    print("Telechargement termine.")
    print(f"  Telecharges      : {compteurs['ok']}")
    print(f"  Deja presents    : {compteurs['saute']}")
    print(f"  Indisponibles    : {compteurs['absent']}")
 
    if compteurs["absent"] > 0:
        print("\nNote : les mois indisponibles ne sont pas encore publies par la TLC.")
 
 
if __name__ == "__main__":
    main()