# Proposition — Système hybride DuckDB (à débattre)

> **Statut : PROPOSITION, pas un fait accompli.** Issue d'un spike d'une soirée (branche `spike/duckdb-hybride`, jetable). Objectif : ouvrir une décision d'équipe, pas merger du code. Le seul point qui engage durablement l'équipe (le dual-adapter dbt) est explicitement marqué comme **next step optionnel**, à décider ensemble.
>
> Chiffres ci-dessous = **mesures réelles** du spike sur `2024-01`, `2024-07`, `2025-01` (9 516 753 trajets), pas des estimations.

---

## 1. L'idée : un pipeline « 3 colonnes », le coût uniquement à droite

L'intuition : aujourd'hui on paie Snowflake (crédits + secrets + latence) à chaque fois qu'on veut *regarder* la donnée ou *tester* un modèle. Or l'exploration et le dev/CI peuvent se faire **localement et gratuitement** sur DuckDB, qui lit les mêmes Parquet. Snowflake reste la **prod** — et c'est la seule colonne où le coût tombe.

```
   EXPLORATION              DEV / CI                    PROD
   (DuckDB + matplotlib)    (DuckDB local)              (Snowflake)
 ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
 │ EDA en SQL          │  │ dbt-duckdb local    │  │ dbt build complet   │
 │ httpfs → Parquet    │  │ tests / lint        │  │ RAW→STAGING→FINAL   │
 │ distant, 0 download  │  │ CI GitHub Actions   │  │ orchestration       │
 │                     │  │ sur Parquet         │  │ tables analytiques  │
 ├────────────────────┤  ├────────────────────┤  ├────────────────────┤
 │ 0 crédit            │  │ 0 crédit            │  │ crédits Snowflake   │
 │ 0 secret            │  │ 0 secret            │  │ secrets requis      │
 │ latence ~2-3 s 1er  │  │ run dbt sub-seconde │  │ latence warehouse   │
 │ scan, puis local    │  │                     │  │ + facturation       │
 └────────────────────┘  └────────────────────┘  └────────────────────┘
        gratuit                 gratuit               ← LE COÛT EST ICI →
```

**Point clé à retenir :** DuckDB ne *remplace pas* Snowflake. Il **déplace vers la gauche** (exploration + CI) tout ce qui n'a pas besoin de tourner en prod, pour ne dépenser des crédits qu'au moment qui compte vraiment : le `dbt build` de production.

---

## 2. Tableau des douleurs résolues (chiffres réels du spike)

| Douleur actuelle | Comment l'hybride la résout | Preuve mesurée ce soir |
|---|---|---|
| **Chaque EDA / requête ad hoc consomme des crédits** Snowflake (warehouse qui démarre, scan facturé) | EDA réécrite en **SQL DuckDB**, lue en local | `scripts/eda_duckdb.py` agrège **9 516 753 trajets** sur 3 mois, **0 crédit Snowflake** |
| **Il faut télécharger ou stager les Parquet** avant de les regarder | `httpfs` lit le Parquet **distant CloudFront** sans aucun download local | `INSTALL httpfs; LOAD httpfs;` suffit ; latence ~**2-3 s** au 1er scan réseau, puis local |
| **La CI a besoin des secrets Snowflake** (clés, compte) → friction sécurité + setup | CI peut tourner sur **DuckDB local** sur un Parquet : **aucun secret** à injecter dans GitHub Actions | Modèle dbt staging buildé **sans connexion Snowflake** |
| **Itérer un modèle dbt = round-trip warehouse** (latence + crédits à chaque `dbt run`) | `dbt-duckdb` build le modèle **en local, instantané** | `dbt run` du modèle staging en **~0,15–0,26 s** (vue), build total **~0,26–0,44 s**, **0 crédit** |
| **Le schema drift** (`cbd_congestion_fee` apparue en 2025) casse les unions naïves | `union_by_name => true` remplit NULL là où la colonne manque (= équivalent DuckDB du `diagonal_relaxed` Polars **et** du `MATCH_BY_COLUMN_NAME` du `COPY INTO` Snowflake) | Preuve : `count(cbd_congestion_fee)` = **0** en 2024-01 et 2024-07, **3 475 226** en 2025-01 (= 100 % du mois) |
| **Vérifier la qualité / réconcilier la facturation** demande des passes coûteuses | Idiomes DuckDB `count(*) FILTER(WHERE …)` + `sum(…) OVER ()` font tout **en une passe locale** | **28,6 %** des lignes (2 725 246 / 9,5 M) en écart de facturation ; **86,4 %** de survie au filtre de nettoyage (8 223 889 / 9 516 753) — cohérent avec l'EDA Polars |

> Les chiffres de réconciliation et de survie **recoupent l'EDA Polars** de référence (~28 %, ~86 %) : DuckDB redonne les mêmes résultats, ce qui valide qu'on peut explorer en local sans rien perdre.

---

## 3. Paliers de risque (adopter par ordre croissant)

Tout n'a pas le même coût de maintenance. On peut s'arrêter à n'importe quel palier.

| Palier | Ce qu'on adopte | Risque / engagement | Verdict |
|---|---|---|---|
| **1 — EDA DuckDB** | `eda_duckdb.py` pour explorer en local | **Faible.** Script autonome, jetable, n'impacte aucun contrat. Gratuit. | **À adopter tout de suite** — bénéfice immédiat, zéro engagement |
| **2 — Tests / CI sur DuckDB** | Faire tourner les tests dbt + lint en CI sur DuckDB local | **Moyen.** Demande de garder le SQL des modèles testés *exécutable sur DuckDB* → discipline, mais sur un périmètre choisi | **À expérimenter** — gros gain CI (rapide, sans secret) pour un coût contenu |
| **3 — dbt dual-adapter complet** | Tous les modèles dbt tournent sur DuckDB **et** Snowflake | **Élevé.** Engage **toute l'équipe** à maintenir la portabilité de **chaque** modèle (voir §4). | **Next step à débattre** — surtout PAS un prérequis |

---

## 4. Le point dur, honnêtement : la portabilité dbt DuckDB ↔ Snowflake

C'est là que la proposition doit être prudente. Le spike a fait tourner **un** modèle staging en dual-adapter, et la portabilité est **partiellement, mais pas totalement, automatique**.

**Ce que dbt absorbe pour nous (les macros cross-db via `adapter.dispatch`) :**
- `{{ dbt.datediff('a','b','minute') }}` compile vers `date_diff('minute', …)` côté DuckDB et vers `DATEDIFF('minute', …)` côté Snowflake. La **fonction native diverge**, le macro la masque. Idem `{{ dbt.date_trunc(...) }}`.
- ⚠️ **Piège de version observé** : depuis `dbt_utils` 1.0, `datediff`/`date_trunc` ont **migré** de `dbt_utils.*` vers le namespace dbt-core `dbt.*`. Écrire `{{ dbt_utils.datediff(...) }}` échoue (`dict object has no attribute datediff`). Il faut `{{ dbt.datediff(...) }}`. À documenter pour l'équipe.

**Ce que dbt n'absorbe PAS — discipline SQL pure, non couverte par Jinja :**
- **Casse PascalCase du Parquet.** `VendorID`, `RatecodeID`, `PULocationID`, `Airport_fee` : DuckDB replie les identifiants non quotés en minuscules. Il faut les **quoter manuellement** (`"RatecodeID"`) puis les aliaser en snake_case pour retomber sur les noms que Snowflake reçoit déjà via `MATCH_BY_COLUMN_NAME`. Aucun macro ne fait ça à notre place.
- **Types divergents.** `tpep_pickup/dropoff_datetime` arrivent en `TIMESTAMP` côté DuckDB, mais en `TIMESTAMP_NTZ` côté Snowflake (RAW). Invisible dans le SQL dbt, **bien réel dans le SQL compilé** et dans toute comparaison/jointure temporelle.
- **Les sources ne sont pas portables.** `source('nyc_taxi','yellow_taxi_trips')` pointe **intrinsèquement** vers Snowflake (`NYC_TAXI_DB.RAW`). La rediriger « en place » vers un Parquet casserait la résolution Snowflake. Dans le spike on a contourné via un **modèle standalone** gardé par `config(enabled=(target.type=='duckdb'))` : il ne tourne que sur la target duckdb, le modèle Snowflake d'origine reste **strictement inchangé** (`git diff` vide). C'est la **friction structurelle** d'un dual-adapter : modèles portables ≠ sources/seeds portables.

**Conclusion du point dur :** la portabilité marche, mais elle a **3 angles morts** (casse, types, sources) qui reposent sur de la discipline humaine, pas sur l'outillage. Généraliser le dual-adapter = accepter cette discipline sur **tous** les modèles et sa charge de maintenance pour **toute** l'équipe.

---

## 5. Recommandation de séquencement (J1 / J2 / J3)

| Jour | Action | Palier |
|---|---|---|
| **J1** | Adopter l'**EDA DuckDB** comme outil d'exploration partagé. Documenter le `httpfs` + dicos TLC. Gain immédiat, zéro engagement. | Palier 1 |
| **J2** | Brancher la **CI sur DuckDB** pour les tests/lint des modèles staging (gratuit, sans secret, rapide). Mesurer le temps de CI gagné. | Palier 2 |
| **J3+** | **Débattre** du dual-adapter complet à la lumière du §4. Décider si la portabilité de *tous* les modèles vaut sa charge de maintenance. | Palier 3 |

> **Le dual-adapter complet est un *next step*, pas un prérequis.** Les paliers 1 et 2 délivrent l'essentiel du bénéfice (explorer + tester sans crédits/secrets) **sans** engager l'équipe sur la maintenance de portabilité du palier 3.

---

## Ce qui reste à décider en équipe

1. **Adopte-t-on l'EDA DuckDB** (palier 1) comme outil d'exploration officiel ? *(reco : oui, coût ~nul)*
2. **Branche-t-on la CI sur DuckDB** (palier 2) ? Sur quel périmètre de modèles commence-t-on ?
3. **Va-t-on jusqu'au dual-adapter complet** (palier 3) ? Qui porte la maintenance de la portabilité (casse PascalCase, types `TIMESTAMP_NTZ`, sources mono-moteur) ? Est-ce que le gain justifie la discipline imposée à tous ?
4. **Convention d'équipe** : si on garde du SQL portable, on fige `{{ dbt.datediff }}` (pas `dbt_utils.*`) et le quoting systématique des identifiants PascalCase.

---

### Annexe — Preuves visuelles (générées par le spike, 0 crédit Snowflake)

- `reports/figures/volume_par_mois_duckdb.png` — volume par mois + drift
- `reports/figures/trips_by_hour_duckdb.png` — trajets par heure (creux ~5 h, pic 18-19 h)
- `reports/figures/valeurs_manquantes_duckdb.png` — valeurs manquantes par colonne

> Référence des chiffres : `scripts/eda_duckdb.py` (EDA DuckDB, 3 mois, httpfs distant) et le modèle dual-adapter `dbt_nyc_taxi/models/staging/stg_yellow_taxi_trips_duckdb.sql`. Aucun secret, aucune donnée, aucun appel Snowflake dans ce spike.
