// Change ce numéro à chaque mise à jour de l'appli pour forcer le rafraîchissement
const VERSION = "hon-v31";
const SHELL = ["./", "index.html", "manifest.json", "icon-192.png", "icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => (k.startsWith("hon-") || /^v\d+$/.test(k)) && k !== VERSION).map(k => caches.delete(k)))));
  self.clients.claim();
});
// Réseau d'abord (toujours la dernière version), cache seulement hors connexion.
// Les pages et fichiers de réglage sont revalidés auprès du serveur (« no-cache ») : sans cela, le navigateur
// peut resservir pendant 10 minutes une ancienne version gardée par GitHub Pages.
// Les données Google Sheets ne passent pas par ici : l'appli les gère elle-même.
// Les deux applis sont sur la même adresse (ritemo.github.io) : chacune ne supprime que ses propres caches.
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  const fresh = e.request.mode === "navigate" || /\.(html|json|js)$/.test(url.pathname) || url.pathname.endsWith("/");
  const req = !fresh ? fetch(e.request)
    : e.request.mode === "navigate" ? fetch(url.href, { cache: "no-cache", credentials: "same-origin" })
    : fetch(e.request, { cache: "no-cache" });
  e.respondWith(
    req.then(r => {
      if (r.ok) { const copy = r.clone(); caches.open(VERSION).then(c => c.put(e.request, copy)); }
      return r;
    }).catch(() => caches.match(e.request).then(r => r || caches.match("index.html")))
  );
});
