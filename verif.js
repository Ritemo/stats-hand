// Vérification automatique de l'appli avant sa mise en ligne (lancée par .github/workflows/verif-deploy.yml).
// L'appli est ouverte dans un vrai navigateur (Chromium) avec les vraies données du Google Sheets, puis :
//   1. toutes les pages sont parcourues (accueil, À la une, journées, matchs, clubs, classements, projection) ;
//   2. on touche ce qui s'ouvre : fiches joueurs et gardiens (toutes les listes), rencontres, articles, débrief, notifications ;
//   3. les débriefs et articles générés sont relus (pas de « undefined », « NaN »...).
// Au moindre problème, le script s'arrête avec le code 1 : la mise en ligne est bloquée et l'ancienne version reste en place.
// Même fichier pour les deux applis (garçons et filles) : il lit les réglages dans la page elle-même.
// Test local sans Internet : MOCK_CSV=<dossier contenant un fichier <gid>.csv par onglet>.
const { chromium } = require("playwright");
const http = require("http"), fs = require("fs"), path = require("path");

const ROOT = path.resolve(process.argv[2] || ".");
const MOCK = process.env.MOCK_CSV || "";
const RESUME = process.env.VERIF_RESUME || "verif-resume.txt";
const pb = [];                                   // problèmes trouvés
const note = (x) => { pb.push(x); console.log("  ✗ " + x); };

// petit serveur local : sert le dépôt comme GitHub Pages
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml", ".webmanifest": "application/manifest+json" };
const srv = http.createServer((q, r) => {
  let f = path.join(ROOT, decodeURIComponent(q.url.split("?")[0]));
  if (!f.startsWith(ROOT)) { r.writeHead(403); return r.end(); }
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, "index.html");
  if (!fs.existsSync(f)) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": TYPES[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(r);
});

(async () => {
  await new Promise((ok) => srv.listen(0, ok));
  const URL0 = `http://127.0.0.1:${srv.address().port}/`;
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const ctx = await browser.newContext({ viewport: { width: 360, height: 780 }, isMobile: true, hasTouch: true, serviceWorkers: "block" });
  if (MOCK) await ctx.route("**/docs.google.com/**", (r) => {
    const g = (r.request().url().match(/gid=(\d+)/) || [])[1], f = path.join(MOCK, g + ".csv");
    return r.fulfill({ status: 200, contentType: "text/csv", body: fs.existsSync(f) ? fs.readFileSync(f, "utf8") : "" });
  });
  const p = await ctx.newPage();
  let ici = "chargement";
  p.on("pageerror", (e) => note(`erreur JavaScript (${ici}) : ${e.message}`));

  // ---- 1. chargement avec les vraies données (3 essais : Google répond parfois lentement)
  let ok = false;
  for (let essai = 1; essai <= 3 && !ok; essai++) {
    await p.goto(URL0 + "#/", { waitUntil: "load" });
    await p.waitForSelector(".tabbar .in", { timeout: 30000 }).catch(() => {});
    ok = await p.evaluate(() => typeof D !== "undefined" && !!D && !D.offline && D.cal.length > 0 && D.players.length > 0).catch(() => false);
    if (!ok) await p.waitForTimeout(5000);
  }
  if (!ok) { note("l'appli n'a pas pu charger les données du Google Sheets (3 essais)"); return fin(browser); }
  const info = await p.evaluate(() => ({ nom: document.title, matchs: D.cal.filter((m) => m.res).length, joueurs: D.players.length }));
  console.log(`${info.nom} : ${info.matchs} matchs joués, ${info.joueurs} joueurs`);

  const go = async (h) => {
    ici = "#/" + h;
    await p.evaluate((h) => { if (typeof closeSheet === "function") closeSheet(); location.hash = "#/" + h; }, h);
    await p.waitForTimeout(80);
  };
  const sheetOuverte = () => p.evaluate(() => { const s = document.querySelector(".sheet"); return !!s && s.classList.contains("open") && s.innerText.trim().length > 40; });

  // ---- 2. toutes les pages
  const routes = await p.evaluate(() => {
    const r = ["", "une", "projection", "general", "classement", "buteurs", "gardiens", "equipes"];
    uneJs().forEach((j) => r.push("une/" + j));
    [...new Set(D.cal.map((m) => m.j))].forEach((j) => r.push("journees/" + j));
    D.cal.forEach((m) => r.push("duel/" + m.j + "/" + slug(m.home)));
    D.clubs.forEach((c) => r.push("club/" + slug(c.name)));
    return r;
  });
  for (const r of routes) {
    await go(r);
    const etat = await p.evaluate(() => ({ large: document.documentElement.scrollWidth > window.innerWidth + 1,
      texte: (document.querySelector("main") || {}).innerText || "", introuvable: /introuvable/i.test((document.querySelector(".page-title") || {}).textContent || "") }));
    if (etat.large) note(`la page #/${r} déborde sur le côté`);
    if (etat.texte.length < 30) note(`la page #/${r} est vide`);
    if (etat.introuvable) note(`la page #/${r} affiche « introuvable »`);
    if (/undefined|NaN|\[object/.test(etat.texte)) note(`la page #/${r} contient un texte cassé (undefined / NaN)`);
  }
  console.log(`${routes.length} pages parcourues`);

  // ---- 3. ce qui s'ouvre
  const toucher = async (route, sel, n, quoi, prep) => {
    await go(route); if (prep) { await p.evaluate(prep); await p.waitForTimeout(80); }
    const nb = await p.$$eval(sel, (x) => x.length);
    if (!nb) { note(`${quoi} : aucune ligne à toucher sur #/${route}`); return; }
    let bons = 0;
    for (let i = 0; i < Math.min(n, nb); i++) {
      await p.evaluate(() => closeSheet()); await p.waitForTimeout(60);
      const el = (await p.$$(sel))[i]; await el.scrollIntoViewIfNeeded(); await el.tap(); await p.waitForTimeout(150);
      if (await sheetOuverte()) bons++;
    }
    if (bons < Math.min(n, nb)) note(`${quoi} (#/${route}) : ${Math.min(n, nb) - bons} fiche(s) sur ${Math.min(n, nb)} ne s'ouvrent pas`);
  };
  const my = await p.evaluate(() => slug(MY_TEAM));
  for (const v of ["champ", "moy", "sept", "club"])
    await toucher("buteurs", "[data-player]", 5, `fiches joueurs, liste « ${v} »`, `ui.buteurs=${JSON.stringify(v)};render()`);
  await toucher("gardiens", "[data-keeper]", 5, "fiches gardiens");
  await toucher("club/" + my, "[data-player],[data-keeper]", 6, "fiches de l'effectif", 'ui.clubTab="effectif";render()');
  await toucher("", "[data-notif]", 1, "fenêtre des notifications");

  // une rencontre du calendrier ouvre son match, un article s'ouvre, le débrief se déplie, la projection s'ouvre
  const etape = async (route, sel, attendu, quoi) => {
    await go(route); const el = await p.$(sel);
    if (!el) { note(`${quoi} : élément absent sur #/${route}`); return; }
    await el.scrollIntoViewIfNeeded(); await el.tap(); await p.waitForTimeout(250);
    if (!(await p.evaluate(attendu))) note(`${quoi} : rien ne se passe au toucher (#/${route})`);
  };
  const jJoue = await p.evaluate(() => Math.max(...D.cal.filter((m) => m.res).map((m) => m.j)));
  await etape("journees/" + jJoue, "button.mrow", () => location.hash.startsWith("#/duel/") && !!document.querySelector(".duel-head"), "rencontre du calendrier");
  await etape("une", "button.une", () => !!document.querySelector(".une-a"), "article À la une");
  await etape("general", ".pj-link", () => location.hash === "#/projection" && document.querySelectorAll(".row.pj").length > 0, "lien vers la projection");
  const duel = await p.evaluate(() => { const m = D.cal.filter((x) => x.res).sort((a, b) => b.j - a.j)[0]; return "duel/" + m.j + "/" + slug(m.home); });
  await etape(duel, "[data-debmore]", () => { const d = document.querySelector(".deb-more"); return !!d && !d.hidden; }, "« Lire la suite » du débrief");

  // ---- 4. textes générés (tous les débriefs et articles)
  ici = "textes";
  const casse = await p.evaluate(() => {
    const out = [], re = /undefined|NaN|null|\[object|  /;
    D.cal.filter((m) => m.res).forEach((m) => { try { const d = debrief(m); const t = [d.title, d.chapo, ...d.paras].join(" ");
      if (re.test(t)) out.push(`débrief J${m.j} ${m.home} : « ${t.match(re)[0]} »`); } catch (e) { out.push(`débrief J${m.j} ${m.home} : ${e.message}`); } });
    uneJs().forEach((j) => { try { const a = journeeArticle(j); const t = [a.title, a.chapo, ...a.paras, a.fig || ""].join(" ");
      if (re.test(t)) out.push(`article J${j} : « ${t.match(re)[0]} »`); } catch (e) { out.push(`article J${j} : ${e.message}`); } });
    try { projection(); } catch (e) { out.push("projection : " + e.message); }
    return out;
  });
  casse.forEach(note);
  return fin(browser);
})().catch((e) => { note("le contrôle lui-même a planté : " + e.message); fin(); });

async function fin(browser) {
  if (browser) await browser.close().catch(() => {});
  srv.close();
  // regroupe les pages touchées par un même défaut, et met les fonctions cassées en premier
  const pages = {}, autres = [];
  [...new Set(pb)].forEach((x) => { const m = x.match(/^la page (#\/\S*) (.*)$/); if (m) (pages[m[2]] = pages[m[2]] || []).push(m[1]); else autres.push(x); });
  const lignes = [...autres, ...Object.entries(pages).map(([k, v]) => v.length > 1 ? `${v.length} pages : ${k} (ex. ${v.slice(0, 3).join(", ")})` : `la page ${v[0]} ${k}`)];
  const txt = pb.length ? `${lignes.length} problème(s) :\n- ` + lignes.slice(0, 12).join("\n- ") : "Aucun problème.";
  fs.writeFileSync(RESUME, txt + "\n");
  console.log(pb.length ? "\nMISE EN LIGNE BLOQUÉE\n" + txt : "\nTout est bon : l'appli peut être mise en ligne.");
  process.exit(pb.length ? 1 : 0);
}
