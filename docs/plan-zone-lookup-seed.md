# Plan — intégrer le lookup de zones TLC (seed `taxi_zone_lookup`)

> But : remplacer les `pu_location_id` bruts de `zone_analysis` par des noms lisibles (Borough, Zone,
> service_zone), via un **seed dbt**. Spec prête à exécuter — sûre et **additive** (les chiffres
> existants ne bougent pas). Bon premier exercice dbt « de bout en bout » (seed + jointure + test).

## La source

Lookup officiel TLC, hébergé sur le **même CDN** que les Parquet (dossier `/misc/`) :

```
https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv
```

265 lignes, grille **figée** (pas de version mensuelle). Schéma :

| Colonne | Exemple | Rôle |
|---|---|---|
| `LocationID` | 132 | clé de jointure ↔ `pu_location_id` / `do_location_id` |
| `Borough` | Queens | arrondissement |
| `Zone` | JFK Airport | nom lisible de la zone |
| `service_zone` | Airports | catégorie (Yellow Zone / Boro Zone / Airports / EWR) |

254 IDs « réels » + codes spéciaux (264/265 = Unknown/N.V., 1 = EWR/Newark).

---

## Impact précis sur le build actuel (analyse, rien ne casse)

DAG actuel : `sources(RAW) → stg (view) → int (table) → 3 marts (table)`. Aucun seed.

- **a) Nouvel objet `TAXI_ZONE_LOOKUP`** (seed = toujours matérialisé en **table**, 265 lignes).
  ⚠️ **Seul changement de config OBLIGATOIRE** : il n'y a **pas** de section `seeds:` dans
  `dbt_project.yml` → par défaut le seed irait dans le schéma du profil (**`PUBLIC`**), pas `STAGING`.
  Il faut donc l'ajouter (voir étape 1).
- **b) `dbt run` vs `dbt build`** : le seed devient une **dépendance amont** de `zone_analysis`.
  ⚠️ `dbt run` **ne charge pas** les seeds → `zone_analysis` échouerait (ref vers table absente).
  Il faut **`dbt build`** (enchaîne seed → models → tests), ou un `dbt seed` initial.
- **c) `zone_analysis` (LEFT JOIN)** : ✅ **aucun impact sur les chiffres**. `locationid` est unique
  dans le lookup → jointure **1:1**, pas de fan-out, pas de double-comptage. `LEFT` (et pas `INNER`)
  **volontaire** : un trajet avec un `pu_location_id` hors lookup reste compté (Borough/Zone = NULL)
  → garantie de non-régression.
- **d) Coût** : négligeable (265 lignes broadcastées sur 40 M → quasi nul ; rechargement du seed trivial).
- **e) Test `relationships`** : ⚠️ **seul vrai risque de build rouge**. Si une donnée a un
  `pu_location_id` absent de [1..265], le test échoue (`severity: error` par défaut). Précautions :
  le poser sur `zone_analysis` (265 lignes, scan trivial) **pas** sur `stg` (scan 40 M), et **démarrer
  en `severity: warn`** jusqu'à confirmation que c'est propre.

**Bilan** : purement additif, sous 3 conditions → schéma du seed = STAGING, utiliser `dbt build`,
garder le `LEFT` + test en `warn` d'abord.

---

## Ce que ça apporte

| Sans lookup | Avec lookup |
|---|---|
| `pu_location_id = 132` | **JFK Airport**, Borough **Queens**, service_zone **Airports** |
| Top zones = entiers illisibles | Top zones **nommées**, exploitables en soutenance |
| Pas d'axe géographique | Analyse par **Borough** (5) et **service_zone** (Airports / Yellow / Boro / EWR) |
| — | Mesure du **taux de zones inconnues** (qualité) |

Usage : agrégations/filtres sur des **noms** (BI, notebook), analyse par arrondissement, et la même
dimension se joint aussi sur `do_location_id` (zone de dépose) pour des flux origine→destination.
Valide directement le KPI « top zones » du brief.

---

## Étapes d'implémentation (3 gestes)

### 1. Configurer le schéma des seeds (OBLIGATOIRE) — `dbt_project.yml`
```yaml
seeds:
  nyc_taxi:
    +schema: STAGING
```

### 2. Déposer le CSV
```bash
mkdir -p dbt_nyc_taxi/seeds
curl -sSL https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv \
  -o dbt_nyc_taxi/seeds/taxi_zone_lookup.csv
```
+ un `dbt_nyc_taxi/seeds/_seeds.yml` (types de colonnes + tests `unique`/`not_null` sur `locationid`) :
```yaml
version: 2
seeds:
  - name: taxi_zone_lookup
    config:
      column_types:
        LocationID: integer
        Borough: varchar
        Zone: varchar
        service_zone: varchar
    columns:
      - name: LocationID
        tests: [unique, not_null]
```

### 3. Joindre dans `marts/zone_analysis.sql`
```sql
select
    m.pu_location_id,
    z.borough,
    z.zone,
    z.service_zone,
    count(*)                       as total_trips,
    round(avg(m.trip_distance), 2) as avg_distance,
    round(avg(m.total_amount), 2)  as avg_revenue,
    round(sum(m.total_amount), 2)  as total_revenue
from {{ ref('int_trip_metrics') }} m
left join {{ ref('taxi_zone_lookup') }} z   -- LEFT : un ID inconnu reste visible
       on m.pu_location_id = z.locationid
group by 1, 2, 3, 4
```

### 4. Remplacer le TODO par un vrai test — `marts/_models.yml`
```yaml
      - name: pu_location_id
        tests:
          - relationships:
              to: ref('taxi_zone_lookup')
              field: locationid
              config:
                severity: warn        # passer en error une fois confirmé propre
```

### Validation
```bash
cd dbt_nyc_taxi
uv run dbt build          # seed → models → tests (PAS dbt run)
# vérifier : zone_analysis expose borough/zone, totaux INCHANGÉS, test relationships en warn
```

---

## Texte d'issue (à créer sur le board)

> **Titre** : `dbt : enrichir zone_analysis avec le lookup de zones TLC (seed)`
> **Labels** : `dbt` `sprint:J3`
> **Contexte** : exposer Borough/Zone/service_zone au lieu des pu_location_id bruts (KPI top zones lisible).
> **DoD** :
> - [ ] `seeds: +schema: STAGING` dans dbt_project.yml
> - [ ] seed `taxi_zone_lookup.csv` + `_seeds.yml` (types + unique/not_null sur LocationID)
> - [ ] `zone_analysis` : LEFT JOIN exposant borough/zone/service_zone, totaux inchangés
> - [ ] test `relationships` (severity warn d'abord) ; `dbt build` vert
