# Exploration ponctuelle : trouve les pages de coupe du Pays Riolais (fichier temporaire).
import re, json, html, requests
UA = {"User-Agent": "Mozilla/5.0"}
def get(u):
    try:
        r = requests.get(u, headers=UA, timeout=30); return r.status_code, r.text
    except Exception as e: return 0, str(e)
def comps(page):
    out = []
    for m in re.finditer(r'<smartfire-component[^>]*?attributes="([^"]*)"', page):
        raw = html.unescape(m.group(1))
        try: out.append(json.loads(raw))
        except Exception: pass
    return out
def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items(): yield from walk(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o[:200]): yield from walk(v, path + f"[{i}]")
    else: yield path, o
for poule in ["https://www.ffhandball.fr/competitions/saison-2026-2027-22/regional/m003-honneur-masculine-32524/poule-191000/journee-1/",
              "https://www.ffhandball.fr/competitions/saison-2026-2027-22/regional/f001-nationale-3f-32422/poule-190560/journee-1/"]:
    s, p = get(poule); print("==", poule, s, len(p))
    for c in comps(p):
        for path, v in walk(c):
            if isinstance(v, str) and ("iolais" in v or "/club" in v or "/equipe" in v): print(path, "=", v[:200])
            if re.search(r"(club|structure|equipe1Id|equipe2Id|ext_equipe)", path, re.I) and v not in (None, ""): print(path, "=", str(v)[:120])
    for h in sorted(set(re.findall(r'href="([^"]*(?:club|equipe|coupe)[^"]*)"', p, re.I)))[:40]: print("href", h)
