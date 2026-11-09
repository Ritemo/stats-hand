// ============ RÉGLAGES DE L'APPLI GARÇONS (dépôt stats-hand) ============
// Seul fichier propre à cette appli : index.html et sw.js sont identiques dans les deux dépôts.
// À déposer une fois ; il n'y a normalement plus jamais besoin d'y toucher.
self.APP = {
  id: "hon",                         // préfixe des mémoires du téléphone et du cache (ne pas changer)
  titre: "Stats Hand HON M-A",       // nom de l'onglet du navigateur
  feminin: false,                    // accords : joueurs, buteurs, gardiens
  marque: ["Honneur", "masculine", "Poule A, saison 2026-2027"],   // en-tête de l'accueil
  championnat: "Honneur masculine, poule A",                        // sous-titre des pages club
  // Google Sheets publié en CSV, et numéro (gid) de chaque onglet lu par l'appli
  sheet: "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQZGLWbKFAw9z2IYBoIqk5LVGNu70HT-mFm3ukchTMOOAyKhEqKV8VTlrHBJEZljLVHzpGTNApMpGM/pub?output=csv",
  gid: { joueurs: "2055642853", gardiens: "1898483188", clubs: "1741053301", journees: "1084857610",
         joueursJ: "1109594874", matchs: "211389371", calendrier: "1933894624" },
  ntfy: "prhb-honneur-r7k2q",        // notifications : Pays Riolais seulement
  ntfyTous: "prhb-honneur-tous-r7k2q",   // notifications : tous les résultats
  cache: "hand-cache",               // copie hors connexion des données
  nomsCourts: {},                    // noms courts particuliers, ex. {"Ent. Saône Mamirolle HB (B)": "Mamirolle"}
  // Notes : gardien entré en cours de match sans arrêt sur la feuille (les buts encaissés à partir de cette minute sont pour lui)
  entete: "#13234F",                // couleur de l'en-tête et des barres du téléphone (bleu nuit : garçons)
  accent: "#3D6BF2",                 // accent décoratif (traits des cartes) ; l'orange reste pour Rioz
  relaisGardiens: [
    { j: 5, nom: "HILAIRE GINDRO Jules", minute: 40 }   // à Doubs Central : Jules entre juste après le dernier arrêt de Mathieu (39'34)
  ]
};
