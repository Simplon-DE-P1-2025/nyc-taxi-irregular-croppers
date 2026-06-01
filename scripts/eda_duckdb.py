"""EDA NYC Taxi en SQL DuckDB (spike hybride — exploration locale, 0 crédit Snowflake).

Réécrit en SQL DuckDB les analyses clés de l'EDA Polars (scripts/explore_data.py) :
volume/mois, valeurs manquantes, anomalies qualité, réconciliation de facturation,
distributions catégorielles, patterns temporels, top zones, survie au filtre de nettoyage.

Démontre deux atouts DuckDB :
  (a) lecture du Parquet DISTANT sans téléchargement via httpfs ;
  (b) schema drift géré par `union_by_name => true` + `filename => true`
      (équivalent du how="diagonal_relaxed" Polars et du MATCH_BY_COLUMN_NAME Snowflake).
      Preuve : count(cbd_congestion_fee) = 0 en 2024, >0 en 2025.

Figures : agrégation en SQL puis .pl() -> matplotlib -> reports/figures/*_duckdb.png
(suffixe _duckdb obligatoire pour ne pas écraser les figures Polars).

Lancer : uv run python scripts/eda_duckdb.py
"""

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- Dictionnaires TLC (COPIÉS de scripts/explore_data.py, déjà corrigés/sourcés).
# Source : Data Dictionary for Yellow Taxi Trip Records, TLC, 18 mars 2025.
# (explore_data.py s'exécute au niveau module => on COPIE les dicos plutôt que de l'importer.)
PAYMENT_TYPE = {
    0: "Flex Fare",
    1: "Carte bancaire",
    2: "Espèces",
    3: "Sans frais",
    4: "Litige",
    5: "Inconnu",
    6: "Trajet annulé",
}
RATECODE = {
    1: "Standard",
    2: "JFK",
    3: "Newark",
    4: "Nassau/Westchester",
    5: "Négocié",
    6: "Trajet groupé",
    99: "Null/inconnu",
}
VENDOR = {
    1: "Creative Mobility",
    2: "Curb Mobility",
    6: "Myle Technologies",
    7: "Helix",
}

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/"
MOIS = ["2024-01", "2024-07", "2025-01"]
URLS = [f"{BASE_URL}yellow_tripdata_{m}.parquet" for m in MOIS]

FIG_DIR = Path("reports/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)


def titre(t: str) -> None:
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def main() -> None:
    con = duckdb.connect()  # base en mémoire — aucun fichier .duckdb persisté

    # --- ATOUT (a) : lecture du Parquet DISTANT sans téléchargement via httpfs.
    con.execute("INSTALL httpfs; LOAD httpfs;")

    # --- ATOUT (b) : vue sur les 3 mois, drift géré par union_by_name ;
    # filename => true pour retrouver le mois d'origine de chaque ligne.
    urls_sql = ", ".join(f"'{u}'" for u in URLS)
    con.execute(
        f"""
        CREATE OR REPLACE VIEW trips AS
        SELECT * FROM read_parquet([{urls_sql}],
                                   union_by_name => true,
                                   filename => true)
        """
    )
    print("Atout (a) httpfs : lecture distante OK (aucun téléchargement local).")
    print(f"Atout (b) union_by_name : {len(MOIS)} mois fusionnés malgré le schema drift.")

    # ------------------------------------------------------------------
    # 1) Volume par mois + PREUVE du drift cbd_congestion_fee
    #    count(col) ignore les NULL => 0 pour 2024, >0 pour 2025.
    # ------------------------------------------------------------------
    titre("1) Volume par mois + preuve du schema drift (cbd_congestion_fee)")
    by_month = con.execute(
        """
        SELECT regexp_extract(filename, '(\\d{4}-\\d{2})', 1) AS mois,
               count(*)                  AS trajets,
               count(cbd_congestion_fee) AS cbd_renseigne
        FROM trips
        GROUP BY 1
        ORDER BY 1
        """
    ).pl()
    print(by_month)
    total_rows = int(by_month["trajets"].sum())
    print(f"\nTotal lignes agrégées (3 mois) : {total_rows:,}")
    drift = {
        r["mois"]: int(r["cbd_renseigne"]) for r in by_month.iter_rows(named=True)
    }
    print(f"Drift cbd_congestion_fee renseigné par mois : {drift}")

    # ------------------------------------------------------------------
    # 2) Valeurs manquantes
    # ------------------------------------------------------------------
    titre("2) Valeurs manquantes (NULL) sur colonnes clés")
    missing = con.execute(
        """
        SELECT count(*)                              AS total,
               count(*) - count(passenger_count)      AS passenger_count_null,
               count(*) - count("RatecodeID")         AS ratecodeid_null,
               count(*) - count(congestion_surcharge) AS congestion_null,
               count(*) - count("Airport_fee")        AS airport_fee_null,
               count(*) - count(cbd_congestion_fee)   AS cbd_null
        FROM trips
        """
    ).pl()
    print(missing)
    miss_row = missing.to_dicts()[0]

    # ------------------------------------------------------------------
    # 3) Anomalies qualité en une passe (idiome FILTER de DuckDB)
    # ------------------------------------------------------------------
    titre("3) Anomalies qualité (count(*) FILTER WHERE ...)")
    anomalies = con.execute(
        """
        SELECT count(*) FILTER (WHERE fare_amount < 0)                               AS fare_negatif,
               count(*) FILTER (WHERE total_amount < 0)                              AS total_negatif,
               count(*) FILTER (WHERE trip_distance = 0)                             AS distance_zero,
               count(*) FILTER (WHERE tpep_pickup_datetime >= tpep_dropoff_datetime) AS duree_incoherente,
               count(*) FILTER (WHERE passenger_count = 0)                           AS passagers_zero,
               count(*) FILTER (WHERE passenger_count IS NULL)                       AS passagers_null
        FROM trips
        """
    ).pl()
    print(anomalies)

    # ------------------------------------------------------------------
    # 4) Réconciliation de facturation : total_amount vs somme des 9 composantes
    #    coïncidence ±congestion_surcharge / ±extra via least(abs(ecart-col),abs(ecart+col))<0.01
    # ------------------------------------------------------------------
    titre("4) Réconciliation de facturation (total_amount vs 9 composantes)")
    recon = con.execute(
        """
        WITH recon AS (
          SELECT *,
            total_amount - (
              coalesce(fare_amount,0) + coalesce(extra,0) + coalesce(mta_tax,0)
              + coalesce(tip_amount,0) + coalesce(tolls_amount,0) + coalesce(improvement_surcharge,0)
              + coalesce(congestion_surcharge,0) + coalesce("Airport_fee",0) + coalesce(cbd_congestion_fee,0)
            ) AS ecart
          FROM trips
        )
        SELECT
          count(*)                                                                  AS total,
          count(*) FILTER (WHERE abs(ecart) > 0.01)                                 AS en_ecart,
          count(*) FILTER (WHERE abs(ecart) > 0.01
                AND least(abs(ecart - coalesce(congestion_surcharge,0)),
                          abs(ecart + coalesce(congestion_surcharge,0))) < 0.01)     AS coincide_cong,
          count(*) FILTER (WHERE abs(ecart) > 0.01
                AND least(abs(ecart - coalesce(extra,0)),
                          abs(ecart + coalesce(extra,0))) < 0.01)                    AS coincide_extra
        FROM recon
        """
    ).pl()
    print(recon)
    rr = recon.to_dicts()[0]
    pct_ecart = 100.0 * rr["en_ecart"] / rr["total"]
    en_ecart = rr["en_ecart"]
    pct_cong = 100.0 * rr["coincide_cong"] / en_ecart if en_ecart else 0.0
    pct_extra = 100.0 * rr["coincide_extra"] / en_ecart if en_ecart else 0.0
    print(
        f"\nÉcart > 0.01 : {rr['en_ecart']:,} lignes ({pct_ecart:.1f} % du total)."
        f"\nParmi les lignes en écart : {pct_cong:.1f} % coïncident ±congestion_surcharge,"
        f" {pct_extra:.1f} % coïncident ±extra."
    )

    # ------------------------------------------------------------------
    # 5) Distributions catégorielles (avec dicos TLC copiés)
    # ------------------------------------------------------------------
    titre("5) Distributions catégorielles (payment_type / RatecodeID / VendorID)")
    pay = con.execute(
        """
        SELECT payment_type,
               count(*)                                           AS trajets,
               round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
        FROM trips GROUP BY payment_type ORDER BY trajets DESC
        """
    ).pl()
    pay = pay.with_columns(
        pay["payment_type"]
        .map_elements(lambda v: PAYMENT_TYPE.get(v, f"? ({v})"), return_dtype=str)
        .alias("libelle")
    )
    print("payment_type :")
    print(pay)

    rate = con.execute(
        """
        SELECT "RatecodeID" AS ratecodeid,
               count(*)                                           AS trajets,
               round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
        FROM trips GROUP BY 1 ORDER BY trajets DESC
        """
    ).pl()
    rate = rate.with_columns(
        rate["ratecodeid"]
        .map_elements(
            lambda v: RATECODE.get(int(v), f"? ({v})") if v is not None else "NULL",
            return_dtype=str,
        )
        .alias("libelle")
    )
    print("\nRatecodeID :")
    print(rate)

    vendor = con.execute(
        """
        SELECT "VendorID" AS vendorid,
               count(*)                                           AS trajets,
               round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct
        FROM trips GROUP BY 1 ORDER BY trajets DESC
        """
    ).pl()
    vendor = vendor.with_columns(
        vendor["vendorid"]
        .map_elements(lambda v: VENDOR.get(v, f"? ({v})"), return_dtype=str)
        .alias("libelle")
    )
    print("\nVendorID :")
    print(vendor)

    # ------------------------------------------------------------------
    # 6) Patterns temporels : trajets par heure de prise en charge
    # ------------------------------------------------------------------
    titre("6) Patterns temporels (trajets par heure de pickup)")
    by_hour = con.execute(
        """
        SELECT extract(hour FROM tpep_pickup_datetime) AS heure,
               count(*)                                AS trajets
        FROM trips
        WHERE tpep_pickup_datetime IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """
    ).pl()
    print(by_hour)

    # ------------------------------------------------------------------
    # 7) Top zones de prise en charge (PULocationID)
    # ------------------------------------------------------------------
    titre("7) Top 10 zones de prise en charge (PULocationID)")
    top_zones = con.execute(
        """
        SELECT "PULocationID" AS pulocationid,
               count(*)       AS trajets
        FROM trips GROUP BY 1 ORDER BY trajets DESC LIMIT 10
        """
    ).pl()
    print(top_zones)

    # ------------------------------------------------------------------
    # 8) Survie au filtre de nettoyage du brief
    # ------------------------------------------------------------------
    titre("8) Survie au filtre de nettoyage")
    survie = con.execute(
        """
        SELECT
          count(*) AS total,
          count(*) FILTER (
              WHERE fare_amount >= 0
                AND total_amount >= 0
                AND trip_distance > 0
                AND tpep_pickup_datetime < tpep_dropoff_datetime
                AND passenger_count > 0
          ) AS survivants
        FROM trips
        """
    ).pl()
    print(survie)
    sr = survie.to_dicts()[0]
    pct_survie = 100.0 * sr["survivants"] / sr["total"]
    print(f"\nTaux de survie : {sr['survivants']:,}/{sr['total']:,} = {pct_survie:.1f} %")

    # ------------------------------------------------------------------
    # 9) Aperçu colonne calculée (futur SQL dbt — date_diff portable)
    # ------------------------------------------------------------------
    titre("9) Aperçu colonne calculée (date_diff ~ dbt_utils.datediff)")
    calc = con.execute(
        """
        SELECT date_diff('minute', tpep_pickup_datetime, tpep_dropoff_datetime) AS trip_duration_min,
               extract(hour FROM tpep_pickup_datetime)                          AS pickup_hour
        FROM trips LIMIT 5
        """
    ).pl()
    print(calc)

    # ==================================================================
    # FIGURES (agrégation SQL -> Polars -> matplotlib, suffixe _duckdb)
    # ==================================================================
    titre("Génération des figures *_duckdb.png")
    figs = []

    # Fig 1 : volume par mois
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(by_month["mois"], by_month["trajets"], color="#1f77b4")
    ax.set_title("Volume de trajets par mois (DuckDB)")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Nombre de trajets")
    ax.ticklabel_format(axis="y", style="plain")
    for i, v in enumerate(by_month["trajets"]):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    p = FIG_DIR / "volume_par_mois_duckdb.png"
    fig.savefig(p, dpi=110)
    plt.close(fig)
    figs.append(str(p.resolve()))

    # Fig 2 : trajets par heure
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(by_hour["heure"], by_hour["trajets"], color="#ff7f0e")
    ax.set_title("Trajets par heure de prise en charge (DuckDB)")
    ax.set_xlabel("Heure")
    ax.set_ylabel("Nombre de trajets")
    ax.set_xticks(range(0, 24))
    fig.tight_layout()
    p = FIG_DIR / "trips_by_hour_duckdb.png"
    fig.savefig(p, dpi=110)
    plt.close(fig)
    figs.append(str(p.resolve()))

    # Fig 3 : valeurs manquantes
    cols_miss = [
        "passenger_count_null",
        "ratecodeid_null",
        "congestion_null",
        "airport_fee_null",
        "cbd_null",
    ]
    vals_miss = [miss_row[c] for c in cols_miss]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(cols_miss, vals_miss, color="#d62728")
    ax.set_title("Valeurs manquantes par colonne (DuckDB)")
    ax.set_ylabel("Nombre de NULL")
    ax.tick_params(axis="x", rotation=30)
    for i, v in enumerate(vals_miss):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    p = FIG_DIR / "valeurs_manquantes_duckdb.png"
    fig.savefig(p, dpi=110)
    plt.close(fig)
    figs.append(str(p.resolve()))

    print("Figures générées :")
    for f in figs:
        print(f"  - {f}")

    con.close()
    print("\nTerminé.")


if __name__ == "__main__":
    main()
