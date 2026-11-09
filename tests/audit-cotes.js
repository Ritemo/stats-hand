// Audit des cotes : ouvre l'appli avec les vraies données et compare les prévisions aux résultats.
// Lancé chaque lundi par .github/workflows/audit-cotes.yml (garçons et filles), résultat envoyé sur ntfy.
// Usage : node tests/audit-cotes.js <dossier de l'appli>   (MOCK_CSV=<dossier> pour tester sans Internet)
const { chromium } = require("playwright");
const http = require("http"), fs = require("fs"), path = require("path");
const ROOT = path.resolve(process.argv[2] || "."), MOCK = process.env.MOCK_CSV || "";
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json" };
const srv = http.createServer((q, r) => {
  let f = path.join(ROOT, decodeURIComponent(q.url.split("?")[0]));
  if (!f.startsWith(ROOT)) { r.writeHead(403); return r.end(); }
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, "index.html");
  if (!fs.existsSync(f)) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": TYPES[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(r);
});
(async () => {
  await new Promise((ok) => srv.listen(0, ok));
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const ctx = await browser.newContext({ serviceWorkers: "block" });
  if (MOCK) await ctx.route("**/docs.google.com/**", (r) => {
    const g = (r.request().url().match(/gid=(\d+)/) || [])[1], f = path.join(MOCK, g + ".csv");
    return r.fulfill({ status: 200, contentType: "text/csv", body: fs.existsSync(f) ? fs.readFileSync(f, "utf8") : "" });
  });
  const p = await ctx.newPage();
  let ok = false;
  for (let essai = 1; essai <= 3 && !ok; essai++) {
    await p.goto(`http://127.0.0.1:${srv.address().port}/#/`, { waitUntil: "load" });
    await p.waitForSelector(".tabbar .in", { timeout: 30000 }).catch(() => {});
    ok = await p.evaluate(() => typeof D !== "undefined" && !!D && !D.offline && D.cal.length > 0).catch(() => false);
  }
  let txt;
  if (!ok) txt = "Données introuvables, audit impossible.";
  else txt = await p.evaluate(() => {
    const a = auditCotes(), f = (x) => String(Math.round(x * 10) / 10).replace(".", ",");
    if (!a) return `${APP.titre} : pas encore de match à auditer.`;
    const last = a.js[a.js.length - 1];
    return `${APP.titre} : ${a.verdict}.\n` +
      `Saison : vainqueur trouvé ${a.ok}/${a.n}, écart prévu ${f(a.dPrev)} pour ${f(a.dReel)} réel (rapport ${f(a.pente)}).\n` +
      `J${last.j} : ${last.ok}/${last.n} vainqueurs, écart prévu ${f(last.dPrev)} pour ${f(last.dReel)} réel.\n` +
      (a.changer ? `À revoir : le réglage ${f(a.best.sh)} ferait mieux que ${f(a.cur)} (demander à Claude).` : "Réglage du modèle : rien à changer.");
  });
  console.log(txt);
  fs.appendFileSync(process.env.AUDIT_OUT || "audit-cotes.txt", txt + "\n\n");
  await browser.close(); srv.close();
})();
