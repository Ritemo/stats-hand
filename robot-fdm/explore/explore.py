import re, json, html, requests, unicodedata
UA = {"User-Agent": "Mozilla/5.0"}
B = "https://www.ffhandball.fr/competitions/saison-2026-2027-22/"
def comps(t):
    for m in re.finditer(r'<smartfire-component([^>]*?)attributes="([^"]*)"', t):
        n = re.search(r"name='([^']*)'", m.group(1))
        try: yield (n.group(1) if n else "?"), json.loads(html.unescape(m.group(2)))
        except Exception: pass
def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")
t = requests.get(B + "coupe-de-france/", headers=UA, timeout=30).text
menu = next(d for n, d in comps(t) if n == "competitions---competition-main-menu")
for c in menu["competitions"]:
    url = B + f"coupe-de-france/{slug(c['libelle'])}-{c['ext_competitionId']}/"
    r = requests.get(url, headers=UA, timeout=30)
    eqs = []; poules = []
    for n, d in comps(r.text):
        if n == "competitions---calendar-button": eqs = [e for e in d.get("equipes", []) if "RIOLAIS" in e.get("libelle", "").upper()]
        if n == "competitions---poule-selector": poules = d.get("poules", [])
    print("##", c["libelle"], r.status_code, url, "RIOZ:", eqs)
    if not eqs: continue
    for p in poules:
        pu = url + f"poule-{p['ext_pouleId']}/"
        t2 = requests.get(pu + "journee-1/", headers=UA, timeout=30).text
        for n, d in comps(t2):
            if n == "competitions---rencontre-list":
                for x in d.get("rencontres", []):
                    if "RIOLAIS" in (x["equipe1Libelle"] + x["equipe2Libelle"]).upper():
                        print("  ", p["libelle"], pu, x["equipe1Libelle"], x.get("equipe1Score"), "-", x.get("equipe2Score"), x["equipe2Libelle"], x["date"], x.get("fdmCode"), x.get("ext_rencontreId"))
