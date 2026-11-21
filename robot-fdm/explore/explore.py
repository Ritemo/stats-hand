import re, json, html, requests
UA = {"User-Agent": "Mozilla/5.0"}
B = "https://www.ffhandball.fr"
cands = ["/competitions/saison-2026-2027-22/equipe-2125610/", "/competitions/saison-2026-2027-22/structure-2426/",
         "/clubs/structure-2426/", "/club/2426/", "/competitions/saison-2026-2027-22/club-2426/",
         "/competitions/saison-2026-2027-22/regional/m003-honneur-masculine-32524/poule-191000/equipe-2125610/",
         "/competitions/saison-2026-2027-22/regional/", "/competitions/saison-2026-2027-22/departemental/", "/competitions/saison-2026-2027-22/national/",
         "/wp-json/", "/recherche/?s=riolais"]
for c in cands:
    try: r = requests.get(B + c, headers=UA, timeout=30, allow_redirects=True)
    except Exception as e: print("ERR", c, e); continue
    t = r.text; print("##", c, r.status_code, r.url, len(t))
    names = set()
    for m in re.finditer(r'<smartfire-component([^>]*?)attributes="([^"]*)"', t):
        raw = html.unescape(m.group(2)); n = re.search(r"name='([^']*)'", m.group(1)); names.add(n.group(1) if n else "?")
        for x in re.finditer(r'[^"]{0,100}(?:[Cc]oupe|COUPE|iolais|IOLAIS)[^"]{0,160}', raw):
            s = x.group(0)
            if "HandballTV" not in s: print("  >", s[:260])
    print("  comps", sorted(names)[:20])
    if c == "/wp-json/":
        try: print("  ns", [k for k in r.json().get("namespaces", [])], [k for k in r.json().get("routes", {}) if "compet" in k or "club" in k][:40])
        except Exception as e: print("  json?", e)
    for h in sorted(set(re.findall(r'/competitions/saison-2026-2027-22/[a-z]+/[a-z0-9\-]*coupe[a-z0-9\-]*/', t)))[:60]: print("  href", h)
