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
print("HREF", sorted(set(re.findall(r'[^"\s]*3266[12][^"\s]*', t)))[:10])
lib = "COUPE DE FRANCE CAISSE D'EPARGNE REGIONALE MASCULINE 2026-2027"
for u in [f"coupe-de-france/017-{slug(lib)}-32662/", f"coupe-de-france/{slug(lib)}-32662/", f"coupe-de-france/017-{slug(lib.replace(chr(39),''))}-32662/"]:
    r = requests.get(B + u, headers=UA, timeout=30); print("TRY", u, r.status_code)
    if r.status_code == 200:
        for n, d in comps(r.text):
            if n.startswith("competitions---") and n not in ("competitions---bottom-bar", "competitions---search-bar", "competitions---saison-selector"):
                print(" C", n, list(d.keys())); s = json.dumps(d, ensure_ascii=False)
                for k in ("poules", "phases", "tours", "rencontres"):
                    if k in d: print("  ", k, s[s.find('"%s"' % k):][:1500])
                i = s.find("IOLAIS"); print("  RIOZ", s[max(0, i-600):i+400] if i >= 0 else "-")
        break
