# Stats Hand : mode d'emploi

Ce dépôt contient l'appli de statistiques de l'équipe **seniors garçons du Pays Riolais HB** (Honneur masculine, poule A) et le **robot** qui remplit automatiquement les statistiques des deux équipes, garçons et filles, à partir des feuilles de match de la fédération.

L'appli des filles (Nationale 3 féminine) est dans le dépôt voisin **stats-n3f**. Elle utilise le même code et le même robot : tout ce qui suit la concerne aussi.

Ce document s'adresse à quelqu'un qui reprendrait l'appli sans connaître son fonctionnement. Aucune compétence en programmation n'est nécessaire pour les gestes courants.

---

## 1. Comment ça marche

```
Site de la FFHandball (résultats, feuilles de match PDF)
        │  lu par le robot (GitHub Actions, plusieurs fois par jour)
        ▼
Google Sheets (un fichier par équipe : onglets clubs, journal du robot...)
        │  publié sur le web en CSV
        ▼
Appli (GitHub Pages)  ──►  téléphones des joueurs, parents, supporters
        │
        └─ notifications sur téléphone (service gratuit ntfy)
```

1. Après chaque match, la table de marque publie la **feuille de match** sur le site de la fédération.
2. Le **robot** la lit : score, buteurs, tirs, arrêts, exclusions, déroulé minute par minute. Il écrit tout dans le Google Sheets de l'équipe concernée, puis envoie les notifications.
3. L'**appli** relit le Google Sheets à chaque ouverture. Les débriefs, articles, cotes et projections sont calculés directement dans l'appli, à partir de ces données.

## 2. Où sont les choses

| Élément | Où | Remarque |
|---|---|---|
| Appli garçons | https://ritemo.github.io/stats-hand/ | dépôt GitHub `Ritemo/stats-hand` |
| Appli filles | https://ritemo.github.io/stats-n3f/ | dépôt GitHub `Ritemo/stats-n3f` |
| Sheets garçons | Google Drive, ID `1J52Ra-9AspvEoIDa4R31qqO0adcvNuylc_y7Hjbj-vo` | propriétaire : Mathieu Cognard |
| Sheets filles | Google Drive, ID `1bFnSlIoJ8UMcl6yyvGi6OhxzJTprp04G0fQuj0fx8i0` | propriétaire : Mathieu Cognard |
| Compte du robot | `robot-fdm@stats-honneur-robot.iam.gserviceaccount.com` | doit être **éditeur** des deux Sheets |
| Clé du robot | GitHub > stats-hand > Settings > Secrets and variables > Actions > secret `GOOGLE_CREDENTIALS` | voir la règle de sécurité ci-dessous |
| Mode du robot | même endroit, onglet Variables : `ROBOT_MODE` (garçons) et `ROBOT_MODE_N3F` (filles) | valeur normale : `reel` |

> **Règle de sécurité.** La clé du robot (un fichier JSON) ne doit jamais être envoyée à quelqu'un, ni copiée dans le dépôt, ni collée dans un message. Elle ne se trouve que dans le secret GitHub. Si elle a fuité : Google Cloud Console > projet `stats-honneur-robot` > IAM > Comptes de service > `robot-fdm` > Clés : supprimer l'ancienne clé, en créer une nouvelle et la coller dans le secret `GOOGLE_CREDENTIALS`.

### Fichiers des dépôts

| Fichier | Rôle | Identique dans les deux dépôts ? |
|---|---|---|
| `index.html` | toute l'appli | oui |
| `sw.js` | fonctionnement hors connexion et mises à jour | oui |
| `config.js` | réglages propres à l'appli : nom, Sheets, garçons ou filles, notifications | **non**, un par dépôt |
| `manifest.json`, `icon-*.png`, `logos/` | nom et icône sur le téléphone, logos des clubs | non |
| `tests/verif.js` | contrôle automatique avant chaque mise en ligne | oui |
| `.github/workflows/verif-deploy.yml` | lance le contrôle, puis la mise en ligne | oui |
| `robot-fdm/robot/` | le robot (Python) et ses réglages `config_honneur.json`, `config_n3f.json` | stats-hand seulement |
| `.github/workflows/robot-fdm.yml` | horaires du robot | stats-hand seulement |

### Horaires du robot (heure de Paris en hiver)

| Quand | Fréquence |
|---|---|
| Tous les jours | une fois, vers 6 h 07 |
| Samedi | toutes les 10 minutes de 17 h 33 à 23 h 53 |
| Dimanche | toutes les 10 minutes de 13 h 03 à 20 h 53 |

En été, tout est une heure plus tard. GitHub peut retarder un passage de quelques minutes, parfois davantage.

### Notifications (appli gratuite ntfy)

Pour recevoir les notifications : installer l'appli **ntfy**, toucher **+** et saisir le nom de l'abonnement.

| Abonnement | Contenu |
|---|---|
| `prhb-honneur-r7k2q` | garçons : match du Pays Riolais et journées complètes |
| `prhb-honneur-tous-r7k2q` | garçons : tous les résultats du championnat |
| `prhb-n3f-r7k2q` | filles : match du Pays Riolais et journées complètes |
| `prhb-n3f-tous-r7k2q` | filles : tous les résultats du championnat |
| `prhb-alerte-r7k2q` | **pour la personne qui gère l'appli** : problèmes du robot ou mise en ligne bloquée |

---

## 3. Gestes courants

### Mettre à jour l'appli
1. Dans chacun des deux dépôts : **Add file > Upload files**, déposer le nouveau `index.html` (et `sw.js` s'il a changé). Ne pas toucher à `config.js`.
2. Valider. Le contrôle automatique se lance tout seul (onglet **Actions**, ligne « Vérification et mise en ligne »). Après 2 à 3 minutes : coche verte, l'appli est en ligne.
3. Sur le téléphone, fermer puis rouvrir l'appli pour voir la nouvelle version.

Si le contrôle trouve un problème, la mise en ligne est bloquée, l'ancienne version reste en place et une alerte part sur `prhb-alerte-r7k2q`.

### Relancer le robot à la main
Dépôt **stats-hand** > **Actions** > « Robot feuilles de match » > **Run workflow**, puis choisir le mode :

| Mode | Effet |
|---|---|
| `reel` | passage normal : importe les feuilles de match pas encore lues |
| `controle` | n'écrit rien dans les onglets clubs, remplit seulement `_Import_Controle` (pour vérifier) |
| `rattrapage` | comme `reel`, et en plus corrige les noms et ajoute les joueurs manquants dans les journées déjà saisies, sans toucher aux chiffres |
| `test-notif` | envoie un message de test sur chaque abonnement ntfy |
| `agrandir-test`, `agrandir` | réservé : a servi à agrandir les tableaux des onglets clubs |

### Corriger une donnée
Corriger directement dans le Google Sheets, dans l'onglet du club. Le robot n'écrit jamais dans une journée déjà remplie pour un club : une correction manuelle n'est pas écrasée. L'appli la prend en compte à la prochaine ouverture (Google met environ 5 minutes à republier).

### Où regarder ce qu'a fait le robot
- Onglet `_Robot_Journal` du Sheets : une ligne par match traité (IMPORTÉ, EN ATTENTE, ERREUR, À CONFIRMER...).
- Fichiers `robot-fdm/robot/derniere_execution_*.txt` du dépôt : le dernier passage.
- Fichiers `robot-fdm/robot/alertes_*.txt` : les problèmes en cours (vides ou absents si tout va bien).

---

## 4. Si ça ne marche plus

| Message ou symptôme | Cause probable | Que faire |
|---|---|---|
| Alerte « Robot : problème », ligne « pas de feuille de match importée plus de 24 h après le match » | match reporté, ou feuille pas encore publiée par la table de marque | vérifier le match sur le site de la fédération. S'il est reporté, rien à faire. Si la feuille existe, relancer le robot en mode `reel` |
| Alerte « Robot : problème », « Le robot s'est arrêté : ... données introuvables sur la page » | le site de la fédération a changé de présentation | le robot doit être adapté (voir plus bas, « Faire évoluer ») |
| Alerte « Robot : problème », « ... invalid_grant », « PERMISSION_DENIED », « 403 » | clé du robot expirée ou supprimée, ou Sheets plus partagé avec le compte du robot | vérifier que le compte du robot est éditeur du Sheets, sinon recréer une clé (voir règle de sécurité) |
| Alerte « Robot : problème », statut « À CONFIRMER » ou « FEUILLE SUSPECTE » | nom de joueur ambigu, ou feuille de match manifestement mal remplie | lire le détail dans `_Robot_Journal`, corriger à la main dans le Sheets si besoin |
| Alerte « Robot : installation impossible » | panne passagère de GitHub ou de Python | relancer le robot ; si ça recommence, attendre quelques heures |
| Alerte « Robot : tout est rentré dans l'ordre » | le problème signalé a disparu | rien |
| Alerte « Mise en ligne bloquée » | le contrôle a trouvé une erreur dans la nouvelle version de l'appli | redéposer la version précédente de `index.html`, ou faire corriger la nouvelle |
| L'appli affiche une ancienne version | le téléphone garde l'ancienne en mémoire | fermer complètement l'appli et la rouvrir, ou toucher le bouton d'actualisation en haut à droite |
| L'appli affiche « Impossible de charger les stats » | pas de réseau, ou Google ne répond pas | réessayer plus tard ; l'appli garde une copie hors connexion |
| Un résultat n'apparaît pas | feuille pas encore publiée, ou robot pas encore passé | attendre le prochain passage, ou relancer le robot en mode `reel` |

Une même panne n'est signalée qu'une fois, pas à chaque passage du robot. Quand elle disparaît, un message « tout est rentré dans l'ordre » le confirme.

---

## 5. Passer à la saison suivante (été)

1. **Ne pas vider ni réutiliser** les Sheets de la saison qui se termine : ils servent d'archive et permettront de comparer les saisons.
2. Pour chaque équipe, créer le nouveau Sheets : Fichier > Créer une copie du Sheets de la saison précédente, puis effacer les chiffres des onglets clubs, `_Matchs`, `_Robot_Journal`, `_Licences` et `_Import_Controle`. Renommer les onglets clubs selon les nouvelles équipes de la poule.
3. Partager chaque nouveau Sheets avec le compte du robot (`robot-fdm@...`) en **éditeur**.
4. Publier chaque Sheets sur le web : Fichier > Partager > Publier sur le web > format CSV. Noter l'adresse publiée et le numéro (`gid`) de chaque onglet lu par l'appli (il apparaît dans l'adresse quand on ouvre l'onglet).
5. Dans chaque dépôt, mettre à jour `config.js` : `sheet`, `gid`, `marque`, `championnat`.
6. Dans `robot-fdm/robot/`, mettre à jour `config_honneur.json` et `config_n3f.json` : `sheet_id`, `poule_url` (adresse de la nouvelle poule sur le site de la fédération), `journees`, et la liste `equipes` (nom sur le site de la fédération > nom de l'onglet).
7. Ajouter les logos des nouveaux clubs dans `logos/` (voir `logos/LISTE-LOGOS.txt` pour le nom des fichiers).
8. Lancer le robot en mode `controle`, vérifier `_Import_Controle`, puis repasser en `reel`.

---

## 6. Faire évoluer l'appli

L'appli et le robot ont été écrits avec l'aide de Claude (Anthropic). Pour une évolution ou une réparation, le plus simple est de fournir à Claude ce mode d'emploi, le fichier concerné (`index.html`, `robot.py`...) et, si besoin, une capture d'écran du problème.

- L'appli tient en un seul fichier, `index.html`, commun aux deux dépôts. Les différences entre garçons et filles sont dans `config.js`.
- Le robot est en Python : `robot.py` (programme principal) et `fdm.py` (lecture des feuilles de match PDF).
- Le contrôle automatique (`tests/verif.js`) empêche la mise en ligne d'une version qui casserait l'appli.
