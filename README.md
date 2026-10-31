# Stats Hand : Honneur masculine, poule A

Appli web (PWA) des statistiques du championnat Honneur masculine, poule A, saison 2026-2027, pour les joueurs du Pays Riolais HB.
Ce dépôt contient aussi **le robot qui remplit les stats des deux championnats** (garçons et filles).

- Appli garçons : https://ritemo.github.io/stats-hand/
- Appli filles : https://ritemo.github.io/stats-n3f/ (dépôt `stats-n3f`, même code, réglages différents)

## Comment ça marche

```
Feuilles de match FFHandball (PDF)
        │  robot (GitHub Actions, ce dépôt)
        ▼
Google Sheets des stats (un par championnat)
        │  publié sur le web en CSV
        ▼
Appli sur GitHub Pages (index.html + config.js)
```

1. Le **robot** (`robot-fdm/robot/robot.py`) lit les rencontres sur ffhandball.fr, télécharge les feuilles de match, et écrit buts, tirs, arrêts et exclusions dans le Google Sheets via un compte de service Google.
2. Le **Google Sheets** est publié sur le web en CSV (Fichier > Partager > Publier sur le web > document entier).
3. L'**appli** lit ces CSV à chaque ouverture et garde une copie hors connexion.

## Les fichiers

| Fichier | Rôle |
|---|---|
| `index.html`, `sw.js` | L'appli. **Identiques** dans `stats-hand` et `stats-n3f` : toute modification se fait dans les deux dépôts. |
| `config.js` | Seul fichier propre à chaque appli : titre, adresse CSV du Sheets, numéros d'onglets (gid), sujets de notification. |
| `manifest.json`, `icon-*.png`, `logos/` | Nom, icônes et logos des clubs. |
| `tests/verif.js` | Test automatique de l'appli dans un vrai navigateur, avec les vraies données. |
| `robot-fdm/robot/robot.py`, `fdm.py` | Le robot et la lecture des PDF. |
| `robot-fdm/robot/config_honneur.json`, `config_n3f.json` | Poule, identifiant du Sheets, correspondance équipes / onglets, pour chaque championnat. |
| `robot-fdm/robot/derniere_execution_*.txt` | Trace du dernier passage du robot. |
| `.github/workflows/robot-fdm.yml` | Horaires du robot. |
| `.github/workflows/verif-deploy.yml` | Test puis mise en ligne de l'appli à chaque modification. |

## Horaires du robot

- Tous les jours vers 7 h (heure de Paris) : horaires, salles, résultats.
- Samedi soir et dimanche après-midi : toutes les 10 minutes pendant les créneaux de match.
- À la main : onglet **Actions > Robot feuilles de match > Run workflow**, avec un mode au choix :
  - `controle` : écrit seulement l'onglet `_Import_Controle` (ce que le robot ferait), ne touche à rien d'autre ;
  - `reel` : remplit les journées encore vides ;
  - `rattrapage` : `reel` + noms officiels et joueurs manquants dans les journées déjà saisies ;
  - `test-notif` : envoie une notification de test ;
  - `agrandir-test` puis `agrandir` : passe chaque onglet club à 30 lignes joueurs et 8 gardiens.

Le robot n'écrit **jamais** dans une journée déjà remplie pour un club.

## Réglages GitHub

*Settings > Secrets and variables > Actions*

| Nom | Type | Valeur |
|---|---|---|
| `GOOGLE_CREDENTIALS` | secret | Contenu complet du fichier JSON de la clé du compte de service. Le compte de service doit être **éditeur** des deux Google Sheets. |
| `ROBOT_MODE` | variable | Mode des passages programmés pour les garçons (`reel` en saison, `controle` pour tester). |
| `ROBOT_MODE_N3F` | variable | Même chose pour les filles. |
| `NOMS_OFFICIELS` | variable | `1` pour réécrire les noms avec l'orthographe de la feuille de match. |

*Settings > Pages > Source* : **GitHub Actions**.

## Onglets techniques créés dans le Sheets

- `_Import_Controle` : ce que le robot écrirait, avec les écarts par rapport aux saisies.
- `_Robot_Journal` : une ligne par match traité (IMPORTÉ, EN ATTENTE, À CONFIRMER, ERREUR).
- `_Licences` : licence vers ligne de chaque joueur. Ne pas modifier, sauf erreur de rattachement.
- `_Matchs` : détails des rencontres (salle, déroulé, mi-temps…).

## Notifications (ntfy.sh, gratuit)

S'abonner dans l'appli ntfy aux sujets :

- `prhb-honneur-r7k2q` : match du Pays Riolais et journées complètes ;
- `prhb-honneur-tous-r7k2q` : tous les résultats ;
- `prhb-n3f-r7k2q` et `prhb-n3f-tous-r7k2q` : la même chose pour les filles ;
- `prhb-alerte-r7k2q` : **alerte technique** quand une mise en ligne est bloquée par le test.

## Tâches courantes

**Modifier l'appli**
1. Modifier `index.html` (et/ou `sw.js`) **dans les deux dépôts**.
2. Déposer les fichiers : le test se lance seul. S'il passe, l'appli est mise en ligne ; sinon l'ancienne version reste en place et une alerte part sur `prhb-alerte-r7k2q`.

**Corriger une stat saisie par le robot** : directement dans le Google Sheets. Le robot ne réécrira pas une journée déjà remplie.

**Nouvelle saison**
1. Créer le nouveau Google Sheets (copie de l'ancien vidé), le partager en éditeur avec le compte de service, le publier en CSV.
2. Dans `config_honneur.json` : `sheet_id`, `poule_url`, `journees` et la liste `equipes`.
3. Dans `config.js` : `sheet` (nouvelle adresse CSV), les `gid` des onglets, `marque` et `championnat`.
4. Ajouter les logos des nouveaux clubs dans `logos/` (voir `LISTE-LOGOS.txt`).
5. Lancer le robot en mode `controle`, vérifier `_Import_Controle`, puis passer `ROBOT_MODE` à `reel`.

**APK Android** : coller l'adresse de l'appli sur pwabuilder.com, puis *Package for stores > Android*.

## Dépannage

| Symptôme | Où regarder |
|---|---|
| Une journée ne se remplit pas | Onglet `_Robot_Journal` du Sheets (EN ATTENTE = feuille pas encore publiée, À CONFIRMER = joueur à rattacher), puis *Actions* sur GitHub. |
| Le robot échoue à chaque passage | *Actions > dernier passage > logs*. Cause la plus fréquente : le site FFHandball a changé sa présentation ou ses PDF. |
| Erreur d'accès au Sheets | Clé du compte de service supprimée ou Sheets plus partagé avec lui : refaire une clé et mettre à jour `GOOGLE_CREDENTIALS`. |
| L'appli affiche d'anciennes données | Vérifier que le Sheets est toujours publié sur le web ; sur le téléphone, fermer et rouvrir l'appli. |
| Mise en ligne bloquée | Lien dans l'alerte `prhb-alerte-r7k2q` ; le résumé du problème est dans les logs de *Vérification et mise en ligne*. |

## Limites gratuites

- **GitHub Actions** : illimité pour un dépôt public.
- **GitHub** désactive les tâches programmées d'un dépôt sans activité pendant 60 jours. Le passage quotidien du robot enregistre une trace, ce qui garde le dépôt actif ; si le robot s'arrête à l'intersaison, le réactiver dans *Actions*.
- **ntfy.sh** : gratuit, sans compte.
