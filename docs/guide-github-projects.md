# Guide — GitHub Projects (notre Kanban)

> Le suivi d'avancement via Kanban est **demandé par le brief**. On utilise **GitHub Projects**
> (lié au repo) : chaque tâche = une **issue**, chaque issue devient une **carte** qu'on déplace.

## 1. Créer le board (une fois, par la personne qui a créé le repo)
- Sur le repo GitHub → onglet **Projects** → **New project** → modèle **Board**.
- Le nommer (ex. `NYC Taxi — Sprint board`).

## 2. Les colonnes (statuts)
```
📥 Backlog   →   🔜 To do   →   🏗️ In progress   →   👀 In review   →   ✅ Done
```
- **Backlog** : tout ce qui reste à faire.
- **To do** : sélectionné pour le sprint du jour.
- **In progress** : quelqu'un bosse dessus (carte assignée).
- **In review** : une PR est ouverte, en attente de relecture.
- **Done** : mergé sur `main`.

## 3. Le cycle d'une tâche (la routine)
1. **Créer une issue** par tâche, claire et petite (ex. « Modèle dbt `daily_summary` »).
2. **L'assigner** à quelqu'un + lui mettre un **label** (voir §4) + l'ajouter au board.
3. Le responsable crée sa **branche** : `feat/daily-summary`.
4. Il ouvre une **PR** en écrivant **`Closes #12`** dans la description → la carte passera en *Done* automatiquement au merge.
5. Review d'un coéquipier → merge sur `main` → l'issue se ferme, la carte file en **Done**.

## 3 bis. Créer une issue (pas à pas)
1. Repo GitHub → onglet **Issues** → bouton **New issue**.
2. **Titre** = verbe + objet, court et clair : *« Charger les Parquet dans RAW »*.
3. **Description** : le contexte + une **« Definition of Done »** en cases à cocher, ex :
   ```
   - [ ] Données 2024-01→03 chargées dans RAW.yellow_taxi_trips
   - [ ] COUNT(*) cohérent
   - [ ] Script versionné dans scripts/
   ```
4. Dans la colonne de droite : **Assignees** (qui s'en charge), **Labels** (cf. §4),
   **Projects** (ajouter au board).
5. **Submit new issue** → la carte apparaît dans le board.

> 💡 Astuce : dans une PR, écrire **`Closes #<numéro>`** lie la PR à l'issue → au merge,
> l'issue se ferme et la carte passe en *Done* automatiquement.

## 4. Labels (pour filtrer et y voir clair)
- **Par sprint** : `sprint:J1` · `sprint:J2` · `sprint:J3`
- **Par domaine** : `ingestion` · `eda` · `dbt` · `ci` · `docs`
- **Par type** : `feat` · `fix` · `docs`

## 5. Automatisations utiles (onglet Workflows du Project)
- *Item added → To do*
- *Pull request opened → In review*
- *Pull request merged → Done*

→ Active-les une fois : les cartes bougent toutes seules, plus besoin de glisser à la main.

## 6. Routine d'équipe
- **Chaque matin (15 min)** : on regarde le board ensemble, on tire les cartes du jour en *To do*.
- **Une carte par personne en *In progress*** à la fois (on finit avant d'en prendre une autre).
- Rien ne se fait **sans issue** : ça garde le board fidèle à la réalité (et ça nourrit la soutenance).

## Exemple de découpage initial (à adapter en réunion)
| Issue | Label | Assigné |
|---|---|---|
| Setup Snowflake reproductible | `sprint:J1` `ingestion` | P1 |
| Script d'ingestion Parquet → RAW | `sprint:J1` `ingestion` | P1 |
| Exploration des données (rapport qualité) | `sprint:J1` `eda` | P2/P3 |
| CI GitHub Actions (squelette) | `sprint:J1` `ci` | Romain |
| Modèles dbt staging + tests | `sprint:J2` `dbt` | P3 |
| Modèles dbt marts (KPIs) | `sprint:J3` `dbt` | P2 |
| Release `v0.1.0` (fin J1) | `ci` | Romain |
