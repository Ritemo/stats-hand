import re, json, html, requests
UA = {"User-Agent": "Mozilla/5.0"}
B = "https://www.ffhandball.fr/competitions/saison-2026-2027-22/"
def menu(path):
    t = requests.get(B + path, headers=UA, timeout=30).text
    for m in re.finditer(r'<smartfire-component([^>]*?)attributes="([^"]*)"', t):
        if "competition-main-menu" in m.group(1): return json.loads(html.unescape(m.group(2))), t
    return None, t
d, _ = menu("regional/")
us = d.get("url_structures"); print("URLS_T", type(us).__name__, json.dumps(us, ensure_ascii=False)[:600])
print("STRUCT", json.dumps(d.get("structure"), ensure_ascii=False)[:300])
print("COMPS", json.dumps(d.get("competitions"), ensure_ascii=False)[:800])
for p in ["coupe-de-france/", "coupe_de_france/"]:
    d2, t = menu(p)
    if d2: print("##", p, "STRUCT", json.dumps(d2.get("structure"), ensure_ascii=False)[:200]); print("  COMPS", json.dumps(d2.get("competitions"), ensure_ascii=False)[:2500]); print("  US", json.dumps(d2.get("url_structures"), ensure_ascii=False)[:600])
    else: print("##", p, "pas de menu", len(t))
