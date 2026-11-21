# Exploration ponctuelle : trouve les pages de coupe du Pays Riolais (fichier temporaire).
import re, json, html, requests
UA = {"User-Agent": "Mozilla/5.0"}
def get(u):
    try:
        r = requests.get(u, headers=UA, timeout=30); return r.status_code, r.text
    except Exception as e: return 0, str(e)
def comps(page):
    out = []
    for m in re.finditer(r'<smartfire-component([^>]*?)attributes="([^"]*)"', page):
        try: out.append((m.group(1), json.loads(html.unescape(m.group(2)))))
        except Exception: pass
    return out
p = get("https://www.ffhandball.fr/competitions/saison-2026-2027-22/regional/m003-honneur-masculine-32524/poule-191000/journee-1/")[1]
for tag, c in comps(p):
    if "equipes" in c:
        print("TAG", tag[:300]); print("KEYS", list(c.keys()))
        for e in c["equipes"]:
            if "iolais" in json.dumps(e).lower(): print("RIOZ", json.dumps(e, ensure_ascii=False)[:1500])
        print("EX", json.dumps(c["equipes"][0], ensure_ascii=False)[:800])
        for k in c:
            if k not in ("equipes", "menus", "rencontres"): print("K", k, json.dumps(c[k], ensure_ascii=False)[:300])
print("URLS", sorted(set(re.findall(r'https://www\.ffhandball\.fr/[a-z\-]+/', p)))[:60])
print("PATTERNS", sorted(set(re.findall(r'/(?:equipe|club|structure|competitions/[^"]*coupe)[^"\s]{0,80}', p)))[:40])
s, q = get("https://www.ffhandball.fr/competitions/saison-2026-2027-22/")
print("SAISON", s, len(q)); print(sorted(set(re.findall(r'/competitions/saison-2026-2027-22/[^"\s&]*coupe[^"\s&]*', q, re.I)))[:80])
for tag, c in comps(q):
    t = json.dumps(c, ensure_ascii=False)
    for m in re.finditer(r'[^"]{0,80}[Cc]oupe[^"]{0,120}', t): print("C", m.group(0)[:200])
