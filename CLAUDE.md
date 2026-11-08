# Stats Hand (seniors garçons, Pays Riolais HB)

Appli PWA (GitHub Pages) des stats du championnat Honneur masculine, poule A, saison 2026-2027, et robot qui remplit les Google Sheets des **deux** équipes (garçons ici, filles dans `stats-n3f`). Détails complets dans le README.

## Qui je suis et comment je travaille

- Mathieu Cognard. Je ne suis pas développeur : je décris ce que je veux, Claude code, teste et pousse.
- Je travaille surtout depuis mon téléphone (sessions cloud Claude Code), avec un abonnement Claude Pro : économise le quota (pas de relectures inutiles de gros fichiers, pas d'outils qui consomment des tokens en arrière-plan).
- Réponds en français, simplement, sans jargon. Jamais de tiret cadratin (caractère U+2014), ni dans les réponses ni dans les fichiers.
- Uniquement des outils et services gratuits (GitHub Actions, GitHub Pages, Google Sheets, ntfy...). Si quelque chose de payant semble nécessaire, demande d'abord.
- Pousse directement sur `main` une fois les tests passés. Pas de branche ni de pull request sauf si je le demande.
- Tu peux prendre les décisions de design et proposer des améliorations : je valide ou corrige ensuite.
- Le README est écrit pour quelqu'un qui reprendrait le projet sans savoir coder : mets-le à jour quand le fonctionnement change.

## Vérifier avant de pousser

- Lance les tests du dépôt (voir ci-dessous).
- Pour toute modification d'interface, ouvre l'appli avec Playwright (MCP déclaré dans `.mcp.json`) au format téléphone (390 x 844) et vérifie l'affichage, puis au format ordinateur si l'appli s'utilise aussi sur PC.
- Pense au cache du service worker (`sw.js`) : change sa version quand les fichiers de l'appli changent, sinon les téléphones gardent l'ancienne.

## Règles propres à ce projet

- Tests : `node tests/verif.js .` (appli). Robot : `robot-fdm/` (Python), lancé par `.github/workflows/robot-fdm.yml`.
- `index.html`, `sw.js` et `tests/` sont **identiques** dans `stats-n3f` : toute modification se reporte dans les deux dépôts, dans la même session. Seul `config.js` diffère.
- Deux applis distinctes (garçons, filles) même si le code est commun : ne pas les fusionner.
- Données : feuilles de match FFHandball (FDME). Disponibles par joueur : buts, tirs tentés, exclusions 2 min. Gardiens : seulement les arrêts, pas les tirs subis individuels, donc le % d'arrêt se calcule au niveau équipe.
- Personne ne saisit de stats en direct pendant les matchs : tout vient du robot ou d'une saisie après coup dans Google Sheets.
- Je suis gardien dans cette équipe.
