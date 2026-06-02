"""
================================================================================
 download_data.py - Telechargement des fichiers Parquet NYC TLC (yellow taxi)
 Projet NYC Taxi. A executer depuis la racine du projet :

     python scripts/download_data.py                 # saute les fichiers existants
     python scripts/download_data.py --force          # retelecharge tout
     python scripts/download_data.py --annees 2025    # une seule annee
     python scripts/download_data.py --mois 1 2 3     # certains mois seulement

 Telecharge dans data/raw/ (dossier ignore par Git, regenerable a la demande).
 La donnee TLC est figee une fois publiee : on saute par defaut ce qui existe.
================================================================================
"""

import argparse
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# --- Configuration -----------------------------------------------------------
BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
DOSSIER_SORTIE = Path("data/raw")
TYPE_TAXI = "yellow"
ANNEES_DEFAUT = [2024, 2025]
MOIS = range(1, 13)
TIMEOUT_SECONDES = 30
NB_TENTATIVES = 3
TAILLE_BLOC = 1024 * 1024


def construire_nom_fichier(annee, mois):
    """Construit le nom du fichier mensuel TLC."""
    return f"{TYPE_TAXI}_tripdata_{annee}-{mois:02d}.parquet"


def construire_url(nom_fichier):
    """Construit l'URL de telechargement du fichier."""
    return f"{BASE_URL}/{nom_fichier}"


def afficher_progression(taille_telechargee, taille_totale):
    """Affiche une barre de progression pendant le telechargement."""
    if taille_totale <= 0:
        mo = taille_telechargee / (1024 * 1024)
        sys.stdout.write(f"\r    {mo:.1f} Mo telecharges")
        sys.stdout.flush()
        return

    pourcent = min(100, taille_telechargee * 100 // taille_totale)
    barres = pourcent // 4
    affichage = "#" * barres + "-" * (25 - barres)
    mo = taille_telechargee / (1024 * 1024)
    mo_total = taille_totale / (1024 * 1024)
    sys.stdout.write(f"\r    [{affichage}] {pourcent:3d}%  ({mo:.1f}/{mo_total:.1f} Mo)")
    sys.stdout.flush()


def supprimer_fichier_temporaire(chemin_temp):
    """Supprime le fichier temporaire s'il existe."""
    try:
        if chemin_temp.exists():
            chemin_temp.unlink()
    except OSError as e:
        print(f"\r    Impossible de supprimer le fichier temporaire : {e}")


def telecharger_vers_temporaire(url, chemin_temp, timeout):
    """Telecharge un fichier vers un chemin temporaire et retourne sa taille attendue."""
    taille_telechargee = 0

    with urllib.request.urlopen(url, timeout=timeout) as reponse:
        taille_attendue = int(reponse.headers.get("Content-Length", 0))
        # Content-Length absent (proxy, transfert chunked) -> 0 : voir valider_fichier_temporaire.
        
        with chemin_temp.open("wb") as fichier:
            while True:
                bloc = reponse.read(TAILLE_BLOC)
                if not bloc:
                    break
                fichier.write(bloc)
                taille_telechargee += len(bloc)
                afficher_progression(taille_telechargee, taille_attendue)

    print()
    return taille_attendue


def valider_fichier_temporaire(chemin_temp, taille_attendue):
    """Valide les controles techniques minimaux du fichier telecharge."""
    taille_locale = chemin_temp.stat().st_size
    if taille_locale == 0:
        raise ValueError("fichier telecharge vide")
    # Choix defensif assume : si le serveur ne renvoie pas l'en-tete
    # Content-Length, taille_attendue vaut 0 et on ne peut pas comparer.
    # Dans ce cas on laisse passer le fichier (controle de taille desactive)
    # plutot que de bloquer un telechargement potentiellement valide.
    # La verification reelle du contenu Parquet se fait a l'etape suivante (EDA / COPY INTO).
    if taille_attendue > 0 and taille_locale != taille_attendue:
        raise ValueError(
            f"taille incomplete ({taille_locale} octets recus, "
            f"{taille_attendue} attendus)"
        )


def telecharger_fichier(annee, mois, force, timeout, nb_tentatives):
    """Telecharge un fichier mensuel.

    Retourne un statut parmi :
    - ok
    - saute
    - absent
    - interdit
    - erreur_reseau
    - erreur_disque
    - erreur_validation
    """
    nom_fichier = construire_nom_fichier(annee, mois)
    url = construire_url(nom_fichier)
    chemin_local = DOSSIER_SORTIE / nom_fichier
    chemin_temp = chemin_local.with_suffix(chemin_local.suffix + ".tmp")

    if chemin_local.exists() and not force:
        print(f"  Deja present, ignore : {nom_fichier}")
        return "saute"

    supprimer_fichier_temporaire(chemin_temp)

    for tentative in range(1, nb_tentatives + 1):
        try:
            print(f"  Telechargement de {nom_fichier} (tentative {tentative}/{nb_tentatives})")
            taille_attendue = telecharger_vers_temporaire(url, chemin_temp, timeout)
            valider_fichier_temporaire(chemin_temp, taille_attendue)
            chemin_temp.replace(chemin_local)
            return "ok"

        except urllib.error.HTTPError as e:
            supprimer_fichier_temporaire(chemin_temp)

            if e.code == 404:
                print(f"\r    Absent (404) : {nom_fichier}{' ' * 30}")
                return "absent"
            if e.code == 403:
                print(f"\r    Interdit ou non publie (403) : {nom_fichier}{' ' * 30}")
                return "interdit"

            print(f"\r    Erreur HTTP {e.code} : {nom_fichier}{' ' * 30}")
            if tentative == nb_tentatives:
                return "erreur_reseau"

        except urllib.error.URLError as e:
            supprimer_fichier_temporaire(chemin_temp)
            print(f"\r    Erreur reseau : {e.reason}{' ' * 30}")
            if tentative == nb_tentatives:
                return "erreur_reseau"

        except TimeoutError as e:
            supprimer_fichier_temporaire(chemin_temp)
            print(f"\r    Timeout reseau : {e}{' ' * 30}")
            if tentative == nb_tentatives:
                return "erreur_reseau"

        except OSError as e:
            supprimer_fichier_temporaire(chemin_temp)
            print(f"\r    Erreur disque/fichier : {e}{' ' * 30}")
            return "erreur_disque"

        except ValueError as e:
            supprimer_fichier_temporaire(chemin_temp)
            print(f"\r    Fichier invalide : {e}{' ' * 30}")
            return "erreur_validation"

        if tentative < nb_tentatives:
            pause = tentative * 2
            print(f"    Nouvelle tentative dans {pause} s...")
            time.sleep(pause)

    return "erreur_reseau"


def valider_annees(parser, annees):
    """Valide les annees demandees."""
    annee_courante = date.today().year

    for annee in annees:
        if annee < 2009 or annee > annee_courante:
            parser.error(
                f"annee invalide : {annee}. "
                f"Choisir une annee entre 2009 et {annee_courante}."
            )


def valider_mois(parser, mois_demandes):
    """Valide les mois demandes."""
    for mois in mois_demandes:
        if mois < 1 or mois > 12:
            parser.error(f"mois invalide : {mois}. Choisir une valeur entre 1 et 12.")


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
        "--mois",
        type=int,
        nargs="+",
        default=list(MOIS),
        help="Mois a telecharger, de 1 a 12 (defaut : tous les mois).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retelecharge meme les fichiers deja presents.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT_SECONDES,
        help=f"Timeout reseau en secondes (defaut : {TIMEOUT_SECONDES}).",
    )
    parser.add_argument(
        "--tentatives",
        type=int,
        default=NB_TENTATIVES,
        help=f"Nombre de tentatives par fichier (defaut : {NB_TENTATIVES}).",
    )
    args = parser.parse_args()

    valider_annees(parser, args.annees)
    valider_mois(parser, args.mois)
    if args.timeout <= 0:
        parser.error("--timeout doit etre strictement positif.")
    if args.tentatives <= 0:
        parser.error("--tentatives doit etre strictement positif.")

    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)

    print(f"Dossier de sortie : {DOSSIER_SORTIE.resolve()}")
    print(f"Annees ciblees    : {args.annees}")
    print(f"Mois cibles       : {args.mois}")
    print(f"Mode force        : {'oui' if args.force else 'non'}")
    print(f"Timeout reseau    : {args.timeout} s")
    print(f"Tentatives        : {args.tentatives}")
    print("-" * 60)

    statuts = [
        "ok",
        "saute",
        "absent",
        "interdit",
        "erreur_reseau",
        "erreur_disque",
        "erreur_validation",
    ]
    compteurs = {statut: 0 for statut in statuts}

    for annee in args.annees:
        print(f"Annee {annee}")
        for mois in args.mois:
            resultat = telecharger_fichier(
                annee=annee,
                mois=mois,
                force=args.force,
                timeout=args.timeout,
                nb_tentatives=args.tentatives,
            )
            compteurs[resultat] += 1

    print("-" * 60)
    print("Telechargement termine.")
    print(f"  Telecharges          : {compteurs['ok']}")
    print(f"  Deja presents        : {compteurs['saute']}")
    print(f"  Absents (404)        : {compteurs['absent']}")
    print(f"  Interdits / non publies (403) : {compteurs['interdit']}")
    print(f"  Erreurs reseau       : {compteurs['erreur_reseau']}")
    print(f"  Erreurs disque       : {compteurs['erreur_disque']}")
    print(f"  Erreurs validation   : {compteurs['erreur_validation']}")

    erreurs_techniques = (
        compteurs["erreur_reseau"]
        + compteurs["erreur_disque"]
        + compteurs["erreur_validation"]
    )

    if compteurs["absent"] > 0 or compteurs["interdit"] > 0:
        print("\nNote : certains mois peuvent ne pas encore etre publies par la TLC.")

    if erreurs_techniques > 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
