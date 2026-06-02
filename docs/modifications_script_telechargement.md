# Modifications du script de téléchargement

**Source de données NYC TLC — `download_data.py`**

Les modifications sont scindées en deux parties : les évolutions de robustesse retenues pour le sprint en cours (périmètre direct de `download_data.py`), et les améliorations d'industrialisation à traiter ultérieurement.

---

## Sprint 1 — Robustesse du téléchargement

Ces douze évolutions composent un téléchargement robuste : gestion des erreurs, résilience réseau et comportement prévisible dans un pipeline.

| Axe de robustesse | N° | Sujet | Prio. | Périmètre script | Commentaire | Modification apportée au code |
|---|---|---|---|---|---|---|
| Téléchargement vers .tmp | 1 | Télécharger vers un fichier temporaire .tmp | Haute | Oui | Évite de considérer un fichier partiel comme valide | Créer `chemin_temp = chemin_local.with_suffix(suffix + ".tmp")` et télécharger vers ce chemin |
| Renommage atomique | 2 | Renommer le .tmp seulement après succès | Haute | Oui | Garantit que le fichier final correspond à un téléchargement terminé | Après validation, appeler `chemin_temp.replace(chemin_local)` |
| Suppression automatique des .tmp | 3 | Supprimer les .tmp en cas d'échec | Haute | Oui | Évite les résidus ambigus | Dans les blocs `except`, supprimer `chemin_temp` s'il existe |
| Vérification taille (non vide) | 4 | Vérifier que le fichier téléchargé n'est pas vide | Moyenne | Oui | Contrôle technique minimal complémentaire | Contrôler `chemin_temp.stat().st_size > 0` |
| Vérification Content-Length | 5 | Vérifier la taille reçue vs Content-Length | Haute | Oui | Détecte les fichiers tronqués sans analyser le contenu | Lire l'en-tête HTTP `Content-Length` et comparer à la taille locale |
| Timeout configurable | 6 | Ajouter un timeout réseau | Haute | Oui | Évite les blocages longs | Remplacer `urlretrieve()` par `urlopen(url, timeout=...)` |
| Retries avec backoff simple | 7 | Ajouter des retries | Moyenne | Oui | Rend le téléchargement plus résilient | Boucle de tentatives avec pause croissante entre chaque essai |
| Gestion distincte des erreurs | 8 | Gérer HTTPError, URLError, OSError | Haute | Oui | Couvre erreurs serveur, réseau, disque, permissions | Blocs `except` dédiés pour distinguer ces familles d'erreurs |
| Statuts explicites | 9 | Distinguer 404, 403, réseau, disque | Moyenne | Oui | Améliore le diagnostic technique | Statuts séparés : `absent`, `interdit`, `erreur_reseau`, `erreur_disque` |
| Validation des arguments | 10 | Valider l'argument `--annees` | Moyenne | Oui | Contrôle du périmètre de téléchargement | Fonction `valider_annees()` appelée après `parse_args()` |
| Validation des arguments | 11 | Ajouter et valider une option `--mois` | Moyenne | Oui | Permet des relances ciblées | Ajouter `--mois` puis vérifier `1 <= mois <= 12` |
| Code de sortie explicite | 12 | Ajouter un code de sortie | Moyenne | Oui | Utile pour automatisation, CI/CD, pipelines | En fin de `main()` : `sys.exit(1)` si erreur, sinon `sys.exit(0)` |

### Justification des évolutions

Pour chaque évolution, l'argument détaille le problème constaté sur le script initial et la raison de la modification.

| Axe de robustesse | N° | Argument |
|---|---|---|
| Téléchargement vers .tmp | 1 | **Téléchargements partiels non détectés.** En cas d'interruption réseau, de fermeture du programme ou de panne système, un fichier incomplet peut rester sur le disque. Le téléchargement dans un fichier temporaire évite qu'un fichier partiel soit considéré comme valide. |
| Renommage atomique | 2 | **Écriture directe dans le fichier final.** Le script écrivait directement dans le fichier définitif. Renommer le fichier temporaire uniquement après succès garantit que seuls des fichiers complets apparaissent dans `data/raw`. |
| Suppression automatique des .tmp | 3 | **Nettoyage des échecs.** Un fichier temporaire abandonné crée une ambiguïté lors des exécutions suivantes. Sa suppression garantit un état propre du répertoire. |
| Vérification taille (non vide) | 4 | **Pas de validation du fichier.** Le contrôle d'une taille strictement positive détecte les échecs les plus évidents, notamment les fichiers vides issus d'un téléchargement interrompu. |
| Vérification Content-Length | 5 | **Téléchargements partiels non détectés.** Comparer la taille réellement reçue à la taille annoncée par le serveur détecte les fichiers tronqués sans analyser le contenu. |
| Timeout configurable | 6 | **Pas de timeout explicite.** Sur un réseau très lent ou bloqué, le script peut rester suspendu longtemps. Un timeout permet d'abandonner proprement la tentative et de relancer. |
| Retries avec backoff simple | 7 | **Incidents temporaires.** Certaines erreurs réseau sont transitoires. Réessayer automatiquement quelques fois augmente la robustesse sans intervention manuelle. |
| Gestion distincte des erreurs | 8 | **Gestion d'erreurs trop limitée.** Le script ne traitait que les erreurs HTTP. Les erreurs réseau, disque ou permissions doivent être distinguées pour un diagnostic fiable. |
| Statuts explicites | 9 | **Le statut « absent » mélangeait plusieurs réalités.** Un fichier non publié (404) n'est pas le même problème qu'une erreur d'accès (403), réseau ou disque. Des statuts distincts améliorent l'exploitation. |
| Validation des arguments | 10 | **Années peu contrôlées.** Le script acceptait des années incohérentes comme 1800 ou 9999. Une validation évite des requêtes inutiles et améliore l'expérience. |
| Validation des arguments | 11 | **Relances ciblées.** Permettre la sélection de mois précis facilite les reprises de téléchargement et évite de solliciter inutilement le serveur. |
| Code de sortie explicite | 12 | **Pas de code de sortie explicite.** Le script se terminait normalement même en cas d'erreur technique. Dans un pipeline, il est utile de distinguer succès complet, succès partiel attendu et échec technique. |

---

## Améliorations d'industrialisation futures

Ces éléments apportent davantage de valeur lorsque le projet entre en phase d'automatisation ou de déploiement. Ils sont volontairement différés pour ne pas alourdir le script à ce stade.

| Axe d'industrialisation | Sujet | Prio. | Périmètre script | Commentaire | Évolution proposée |
|---|---|---|---|---|---|
| Validation du format | Validation du Parquet avec PyArrow | Moyenne | Non (ou plus tard) | Vérifie que le fichier est réellement un Parquet exploitable | Métadonnées `pq.read_metadata()` ou validation à l'ingestion |
| Logging structuré | Remplacer les print() par logging | Moyenne | Plus tard | Facilite le suivi dans Airflow, cron, Docker, CI/CD | Module logging avec niveaux INFO / WARNING / ERROR |
| Tests automatisés | Tests unitaires du téléchargement | Moyenne | Plus tard | Sécurise les évolutions futures | Mocks des appels réseau, tests des erreurs et fichiers temporaires |
| Configuration externalisée | Déplacer la configuration en YAML / .env | Faible | Plus tard | Facilite le changement d'environnement ou de dataset | Externaliser URL, années, type de taxi, timeout, retries |
| Monitoring | Historiser les téléchargements | Faible | Plus tard | Permet de tracer les exécutions | Journal CSV, SQLite ou logs structurés |
| Observabilité | Ajouter des métriques | Faible | Plus tard | Utile pour les pipelines industrialisés | Nombre de fichiers, durée, volume téléchargé |

### Justification des évolutions

Pour chaque axe, l'argument précise la limite actuelle et l'intérêt de l'évolution dans un contexte industrialisé.

| Axe d'industrialisation | Argument |
|---|---|
| Validation du fichier Parquet | **Pas de validation du contenu.** Un fichier peut avoir la bonne taille tout en étant illisible ou corrompu. Vérifier la structure Parquet sécurise les étapes suivantes du pipeline. |
| Logging structuré | **Pas de logs structurés.** Les print() suffisent pour un usage simple mais restent limités pour le suivi en production, la CI/CD ou l'orchestration. |
| Tests automatisés | **Régression fonctionnelle.** Les tests garantissent que les futures modifications ne cassent pas la logique de téléchargement, de reprise ou de gestion des erreurs. |
| Configuration externalisée | **Configuration figée dans le code.** Type de taxi, URLs ou timeouts gagneraient à être configurables sans modifier le code source. |
| Monitoring / Historisation | **Absence de traçabilité.** Conserver un historique des téléchargements facilite le diagnostic et le suivi opérationnel. |
| Observabilité / Métriques | **Visibilité limitée sur l'exécution.** Les métriques permettent de suivre volumes, durées d'exécution et taux d'échec. |
