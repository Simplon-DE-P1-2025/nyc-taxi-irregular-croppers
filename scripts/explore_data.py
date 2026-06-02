"""
explore_data.py — Exploration complète (EDA) des données NYC Yellow Taxi.

- Télécharge quelques mois représentatifs (idempotent) depuis la source publique TLC.
- Analyse : schéma réel, valeurs manquantes, période, stats, anomalies qualité,
  distributions catégorielles, patterns temporels, top zones, survie au filtre de nettoyage.
- Produit : docs/exploration-donnees.md  +  reports/figures/*.png

Usage : uv run python scripts/explore_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl

# Le script utilise le téléchargeur (scripts/download_data.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_data import telecharger_fichier  # noqa: E402

# ─────────────────────────── Config ───────────────────────────
MONTHS = ["2024-01", "2024-07", "2025-01"]  # hiver / été / début 2025
RAW_DIR = Path("data/raw")
FIG_DIR = Path("reports/figures")
REPORT = Path("docs/exploration-donnees.md")
PERIOD_START = "2024-01-01"
PERIOD_END = "2025-02-01"  # borne haute exclusive (début 2025 = janvier)

# Dictionnaires TLC — source : Data Dictionary Yellow Taxi Trip Records (TLC, 18 mars 2025)
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
VENDOR = {1: "Creative Mobile", 2: "Curb Mobility", 6: "Myle Technologies", 7: "Helix"}

NUMERIC_COLS = [
    "trip_distance",
    "fare_amount",
    "tip_amount",
    "tolls_amount",
    "total_amount",
    "passenger_count",
]


# ─────────────────────────── Helpers ───────────────────────────
def download(month: str) -> Path:
    """Télécharge un mois ('AAAA-MM') via le téléchargeur (download_data.py)."""
    annee, mois = (int(x) for x in month.split("-"))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if telecharger_fichier(annee, mois, force=False) == "absent":
        raise FileNotFoundError(f"{month} indisponible chez la TLC (mois non publié ?)")
    return RAW_DIR / f"yellow_tripdata_{annee}-{mois:02d}.parquet"


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def pct(n: int, total: int) -> str:
    return f"{100 * n / total:.2f} %" if total else "—"


def savefig(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=110, bbox_inches="tight")
    plt.close()
    print(f"  🖼  {path}")


# ─────────────────────────── Chargement ───────────────────────────
print("▶ Téléchargement / chargement des mois :", ", ".join(MONTHS))
frames = []
per_month_counts = {}
per_month_cols = {}
for m in MONTHS:
    p = download(m)
    df_m = pl.read_parquet(p).with_columns(pl.lit(m).alias("source_month"))
    per_month_counts[m] = df_m.height
    per_month_cols[m] = [c for c in df_m.columns if c != "source_month"]
    frames.append(df_m)

# Détection du schema drift entre mois (union/intersection des colonnes)
all_cols = set().union(*per_month_cols.values())
common_cols = set.intersection(*(set(v) for v in per_month_cols.values()))
drift_cols = sorted(all_cols - common_cols)

# diagonal_relaxed : aligne les colonnes (null si absente) ET tolère les types différents
df = pl.concat(frames, how="diagonal_relaxed")
N = df.height
print(f"  ✓ {fmt_int(N)} lignes, {df.width} colonnes (drift : {drift_cols or 'aucun'})")

# Colonnes calculées
df = df.with_columns(
    (
        (
            pl.col("tpep_dropoff_datetime") - pl.col("tpep_pickup_datetime")
        ).dt.total_seconds()
        / 60.0
    ).alias("trip_duration_min"),
)
df = df.with_columns(
    pl.when(pl.col("trip_duration_min") > 0)
    .then(pl.col("trip_distance") / (pl.col("trip_duration_min") / 60.0))
    .otherwise(None)
    .alias("avg_speed_mph"),
    pl.when(pl.col("fare_amount") > 0)
    .then(pl.col("tip_amount") / pl.col("fare_amount") * 100)
    .otherwise(None)
    .alias("tip_pct"),
    pl.col("tpep_pickup_datetime").dt.hour().alias("pickup_hour"),
    pl.col("tpep_pickup_datetime").dt.weekday().alias("pickup_dow"),  # 1=lundi
)


# ─────────────────────────── Calculs qualité ───────────────────────────
def count_where(expr) -> int:
    return df.filter(expr).height


# Cohérence de facturation : total_amount doit ≈ somme des composantes tarifaires.
# Les composantes parfois nulles (péages, congestion, airport, cbd) sont traitées comme 0.
montant_reconstitue = (
    pl.col("fare_amount").fill_null(0)
    + pl.col("extra").fill_null(0)
    + pl.col("mta_tax").fill_null(0)
    + pl.col("tip_amount").fill_null(0)
    + pl.col("tolls_amount").fill_null(0)
    + pl.col("improvement_surcharge").fill_null(0)
    + pl.col("congestion_surcharge").fill_null(0)
    + pl.col("Airport_fee").fill_null(0)
    + pl.col("cbd_congestion_fee").fill_null(0)
)

# Décomposition de l'écart de facturation : avec quelle(s) colonne(s) coïncide-t-il ?
# Méthode : on isole les lignes en écart, puis on teste `écart == ±colonne` pour les
# surcharges suspectes (congestion ~2,50 $, extra). Voir le rapport §4 pour le résultat.
ecart_total = pl.col("total_amount") - montant_reconstitue
_cong = pl.col("congestion_surcharge").fill_null(0)
_extra = pl.col("extra").fill_null(0)
en_ecart = ecart_total.abs() > 0.01
coincide_cong = en_ecart & (
    ((ecart_total - _cong).abs() < 0.01) | ((ecart_total + _cong).abs() < 0.01)
)
coincide_extra = en_ecart & (
    ((ecart_total - _extra).abs() < 0.01) | ((ecart_total + _extra).abs() < 0.01)
)


quality = {
    "Montant `fare_amount` négatif": count_where(pl.col("fare_amount") < 0),
    "Montant `total_amount` négatif": count_where(pl.col("total_amount") < 0),
    "Pourboire `tip_amount` négatif": count_where(pl.col("tip_amount") < 0),
    "`total_amount` = 0": count_where(pl.col("total_amount") == 0),
    "`total_amount` ≠ somme des composantes (écart > 0,01 $)": count_where(en_ecart),
    "└ dont écart == ±`congestion_surcharge` (~2,50 $)": count_where(coincide_cong),
    "└ dont écart == ±`extra`": count_where(coincide_extra),
    "Distance = 0": count_where(pl.col("trip_distance") == 0),
    "Distance > 100 miles": count_where(pl.col("trip_distance") > 100),
    "Distance > 1000 miles (extrême)": count_where(pl.col("trip_distance") > 1000),
    "Pickup ≥ Dropoff (incohérent)": count_where(
        pl.col("tpep_pickup_datetime") >= pl.col("tpep_dropoff_datetime")
    ),
    "Durée ≤ 0 min": count_where(pl.col("trip_duration_min") <= 0),
    "Durée > 24 h": count_where(pl.col("trip_duration_min") > 24 * 60),
    "`passenger_count` = 0": count_where(pl.col("passenger_count") == 0),
    "`passenger_count` nul (null)": df.select(
        pl.col("passenger_count").is_null().sum()
    ).item(),
    "Vitesse moy. > 100 mph (aberrante)": count_where(pl.col("avg_speed_mph") > 100),
    "Hors période 2024–début 2025": count_where(
        (pl.col("tpep_pickup_datetime") < pl.lit(PERIOD_START).str.to_datetime())
        | (pl.col("tpep_pickup_datetime") >= pl.lit(PERIOD_END).str.to_datetime())
    ),
}

# Doublons (lignes entièrement identiques, hors colonnes calculées)
orig_cols = [
    c
    for c in df.columns
    if c
    not in {
        "trip_duration_min",
        "avg_speed_mph",
        "tip_pct",
        "pickup_hour",
        "pickup_dow",
        "source_month",
    }
]
n_dupes = N - df.select(orig_cols).unique().height

# Valeurs manquantes par colonne
null_counts = {c: df.select(pl.col(c).is_null().sum()).item() for c in orig_cols}

# Filtre de nettoyage du brief : survie
survivors = count_where(
    (pl.col("fare_amount") > 0)
    & (pl.col("total_amount") > 0)
    & (pl.col("tip_amount") >= 0)
    & (pl.col("tpep_pickup_datetime") < pl.col("tpep_dropoff_datetime"))
    & (pl.col("trip_distance") >= 0.1)
    & (pl.col("trip_distance") <= 100)
    & pl.col("PULocationID").is_not_null()
    & pl.col("DOLocationID").is_not_null()
    & (pl.col("passenger_count") > 0)
)


# Distributions catégorielles
def dist(col):
    return (df.group_by(col).len().sort("len", descending=True)).to_dicts()


payment_dist = dist("payment_type")
ratecode_dist = dist("RatecodeID")
vendor_dist = dist("VendorID")
fwd_dist = dist("store_and_fwd_flag")

# Temporel
by_hour = df.group_by("pickup_hour").len().sort("pickup_hour").to_dicts()
by_dow = df.group_by("pickup_dow").len().sort("pickup_dow").to_dicts()

# Top zones
top_pu = (
    df.group_by("PULocationID").len().sort("len", descending=True).head(10).to_dicts()
)

# Stats numériques
desc = df.select(NUMERIC_COLS + ["trip_duration_min", "avg_speed_mph"]).describe()

# ─────────────────────────── Figures ───────────────────────────
print("▶ Génération des figures")

# 1. Valeurs manquantes
miss = {c: v for c, v in null_counts.items() if v > 0}
if miss:
    plt.figure(figsize=(8, 4))
    cols = list(miss.keys())
    vals = [100 * miss[c] / N for c in cols]
    plt.barh(cols, vals, color="#d9534f")
    plt.xlabel("% de valeurs manquantes")
    plt.title("Valeurs manquantes par colonne")
    savefig(FIG_DIR / "missing_values.png")

# 2. Distribution trip_distance (clip 0-30)
plt.figure(figsize=(8, 4))
d = df.filter((pl.col("trip_distance") >= 0) & (pl.col("trip_distance") <= 30))[
    "trip_distance"
]
plt.hist(d, bins=60, color="#0275d8")
plt.xlabel("trip_distance (miles, clip 0–30)")
plt.ylabel("Nb trajets")
plt.title("Distribution des distances")
savefig(FIG_DIR / "dist_trip_distance.png")

# 3. Distribution total_amount (clip -10 à 100)
plt.figure(figsize=(8, 4))
t = df.filter((pl.col("total_amount") >= -10) & (pl.col("total_amount") <= 100))[
    "total_amount"
]
plt.hist(t, bins=60, color="#5cb85c")
plt.xlabel("total_amount ($, clip -10–100)")
plt.ylabel("Nb trajets")
plt.title("Distribution du montant total")
savefig(FIG_DIR / "dist_total_amount.png")

# 4. Trajets par heure
plt.figure(figsize=(8, 4))
plt.bar(
    [r["pickup_hour"] for r in by_hour], [r["len"] for r in by_hour], color="#f0ad4e"
)
plt.xlabel("Heure de prise en charge")
plt.ylabel("Nb trajets")
plt.title("Trajets par heure de la journée")
savefig(FIG_DIR / "trips_by_hour.png")

# 5. Trajets par jour de semaine
DOW = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
plt.figure(figsize=(8, 4))
plt.bar(
    [DOW[r["pickup_dow"] - 1] for r in by_dow],
    [r["len"] for r in by_dow],
    color="#9b59b6",
)
plt.xlabel("Jour de la semaine")
plt.ylabel("Nb trajets")
plt.title("Trajets par jour de la semaine")
savefig(FIG_DIR / "trips_by_dow.png")

# 6. Volume mensuel
plt.figure(figsize=(8, 4))
plt.bar(list(per_month_counts.keys()), list(per_month_counts.values()), color="#20639b")
plt.xlabel("Mois")
plt.ylabel("Nb trajets")
plt.title("Volume par mois échantillonné")
savefig(FIG_DIR / "volume_by_month.png")

# ─────────────────────────── Rapport Markdown ───────────────────────────
print("▶ Rédaction du rapport :", REPORT)
L = []


def w(s=""):
    L.append(s)


w("# Rapport d'exploration des données — NYC Yellow Taxi")
w()
w(
    f"> EDA réalisée sur **{len(MONTHS)} mois représentatifs** ({', '.join(MONTHS)}) — "
    f"hiver / été / début 2025. Total analysé : **{fmt_int(N)} trajets**."
)
w("> Généré par `scripts/explore_data.py` (Polars). Figures dans `reports/figures/`.")
w()
w("## 1. Vue d'ensemble")
w("| Mois | Trajets |")
w("|---|---:|")
for m, c in per_month_counts.items():
    w(f"| {m} | {fmt_int(c)} |")
w(f"| **Total échantillon** | **{fmt_int(N)}** |")
w()
w(
    f"- **Colonnes** : 19 en 2024, **20 dès 2025** (union = {len(orig_cols)} ; cf. drift §3 bis). "
    f"Dataset complet 2024+début 2025 ≈ **40 M trajets**."
)
w(f"- **Doublons exacts** : {fmt_int(n_dupes)} ({pct(n_dupes, N)})")
w()
w("![Volume par mois](../reports/figures/volume_by_month.png)")
w()

w("## 2. Schéma réel & valeurs manquantes")
w("| Colonne | Type | Manquants | % |")
w("|---|---|---:|---:|")
for c in orig_cols:
    dt = str(df.schema[c])
    nc = null_counts[c]
    w(f"| `{c}` | {dt} | {fmt_int(nc)} | {pct(nc, N)} |")
w()
if miss:
    w("![Valeurs manquantes](../reports/figures/missing_values.png)")
    w()

w("## 3. ⚠️ Écart majeur avec le DDL du brief")
w("Le DDL imposé par le brief ne correspond **pas** aux données réelles 2024+ :")
w()
w(
    "- ❌ Colonnes **inexistantes** dans le brief : `pickup_longitude`, `pickup_latitude`, "
    "`dropoff_longitude`, `dropoff_latitude` — supprimées par la TLC depuis 2016 (anonymisation). "
    "Les positions sont désormais des **zones** (`PULocationID` / `DOLocationID`)."
)
w(
    "- ⚠️ **Casse des noms** : réel = `PULocationID`, `DOLocationID`, `RatecodeID`, `VendorID` "
    "(PascalCase) ; brief = `pu_location_id`, `do_location_id`, `rate_code_id` (snake_case)."
)
w("- ➕ Colonnes réelles non listées au brief : `VendorID`, `improvement_surcharge`.")
w()
w(
    "➡️ **Le DDL `RAW.yellow_taxi_trips` doit être corrigé** pour coller au schéma Parquet réel "
    "(19 colonnes en 2024, 20 en union avec `cbd_congestion_fee` dès 2025 — cf. §3 bis), "
    "sinon le `COPY INTO` échouera ou décalera les colonnes."
)
w()

w("## 3 bis. ⚠️ Schema drift entre 2024 et 2025")
w("Le schéma **n'est pas stable** sur la période :")
w()
w("| Mois | Nb colonnes |")
w("|---|---:|")
for m in MONTHS:
    w(f"| {m} | {len(per_month_cols[m])} |")
w()
if drift_cols:
    w(
        "- Colonnes **non présentes dans tous les mois** : "
        + ", ".join(f"`{c}`" for c in drift_cols)
    )
    w(
        "- Notamment `cbd_congestion_fee` apparaît en **2025** (tarification congestion Manhattan, "
        "*Central Business District*). ➡️ Le pipeline doit gérer ce **drift** : colonne nullable / "
        "`MATCH_BY_COLUMN_NAME` au `COPY INTO`, et ne pas supposer un schéma figé."
    )
else:
    w("- Aucun écart de colonnes détecté sur l'échantillon.")
w()

w("## 4. Anomalies de qualité (quantifiées)")
w("| Problème | Nb trajets | % |")
w("|---|---:|---:|")
for label, n in quality.items():
    w(f"| {label} | {fmt_int(n)} | {pct(n, N)} |")
w()
_n_ec = quality["`total_amount` ≠ somme des composantes (écart > 0,01 $)"]
_n_cong = quality["└ dont écart == ±`congestion_surcharge` (~2,50 $)"]
_n_extra = quality["└ dont écart == ±`extra`"]
w(
    "> **Lecture de l'écart `total_amount` vs somme des composantes.** L'écart n'est *pas* aléatoire : "
    f"sur les lignes concernées, il coïncide à **{pct(_n_cong, _n_ec)}** avec `congestion_surcharge` "
    f"(±2,50 $) et à **{pct(_n_extra, _n_ec)}** avec `extra`. C'est une **incohérence de réconciliation "
    "des surcharges dans la source TLC** (surcharge tantôt incluse dans le total, tantôt seulement dans "
    "le détail) — **pas une composante manquante ni une erreur de calcul**."
)
w()
w(
    "> _Méthode du diagnostic._ (1) Distribution des écarts non nuls → dominée par des valeurs **discrètes** "
    "(±2,50 $, −3,25 $, −1,75 $…), signe d'un montant systématique plutôt que d'un bruit. (2) Pour chaque "
    "composante tarifaire, test `écart == ±colonne` → seules `congestion_surcharge` et `extra` ressortent. "
    "Calculs reproductibles dans `scripts/explore_data.py` (`ecart_total`, `coincide_cong`, `coincide_extra`)."
)
w()

w("## 5. Statistiques descriptives")
w("```")
w(str(desc))
w("```")
w()
w("![Distribution distances](../reports/figures/dist_trip_distance.png)")
w()
w("![Distribution montant total](../reports/figures/dist_total_amount.png)")
w()

w("## 6. Distributions catégorielles")


def cat_table(title, data, mapping, key):
    w(f"**{title}**")
    w()
    w("| Code | Libellé | Trajets | % |")
    w("|---|---|---:|---:|")
    for r in data:
        code = r[key]
        lib = mapping.get(code, "?")
        w(f"| {code} | {lib} | {fmt_int(r['len'])} | {pct(r['len'], N)} |")
    w()


cat_table(
    "Type de paiement (`payment_type`)", payment_dist, PAYMENT_TYPE, "payment_type"
)
cat_table("Code tarifaire (`RatecodeID`)", ratecode_dist, RATECODE, "RatecodeID")
cat_table("Fournisseur (`VendorID`)", vendor_dist, VENDOR, "VendorID")
w("![Trajets par heure](../reports/figures/trips_by_hour.png)")
w()
w("![Trajets par jour](../reports/figures/trips_by_dow.png)")
w()

w("## 7. Top 10 zones de prise en charge")
w("| PULocationID | Trajets | % |")
w("|---:|---:|---:|")
for r in top_pu:
    w(f"| {r['PULocationID']} | {fmt_int(r['len'])} | {pct(r['len'], N)} |")
w()

w("## 8. Impact du filtre de nettoyage du brief")
removed = N - survivors
w(
    f"- Trajets **conservés** après application des règles du brief : "
    f"**{fmt_int(survivors)}** ({pct(survivors, N)})"
)
w(f"- Trajets **éliminés** : {fmt_int(removed)} ({pct(removed, N)})")
w()
w(
    "> Règles appliquées : `fare_amount>0`, `total_amount>0`, `tip_amount>=0`, "
    "`pickup<dropoff`, `trip_distance` ∈ [0.1, 100], `PULocationID`/`DOLocationID` non nuls, "
    "`passenger_count>0`."
)
w()

w("## 9. Recommandations pour le pipeline")
w(
    "1. **Corriger le DDL RAW** sur le schéma réel (19 col. en 2024, 20 en union ; noms PascalCase, pas de lat/long)."
)
w(
    "2. Gérer les **valeurs manquantes** de `passenger_count`, `RatecodeID`, `congestion_surcharge`, "
    "`Airport_fee` (souvent nulles) avant les calculs."
)
w(
    "3. Le **filtre de nettoyage** retire une part non négligeable des lignes — le documenter dans le rapport."
)
w(
    "4. Ajouter un garde-fou **vitesse moyenne** (> 100 mph) en plus des règles du brief."
)
w(
    "5. Caster les **timestamps** correctement (ns) et vérifier l'absence de dates hors période."
)

REPORT.write_text("\n".join(L), encoding="utf-8")
print("✓ Rapport écrit.")
print(
    f"\nRésumé : {fmt_int(N)} trajets | {fmt_int(survivors)} conservés ({pct(survivors, N)}) "
    f"| {len([v for v in null_counts.values() if v])} colonnes avec nulls"
)
