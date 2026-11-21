import re, json, html, requests
UA = {"User-Agent": "Mozilla/5.0"}
B = "https://www.ffhandball.fr"
for c in ["/competitions/saison-2026-2027-22/regional/", "/competitions/saison-2026-2027-22/departemental/"]:
    t = requests.get(B + c, headers=UA, timeout=30).text
    for m in re.finditer(r'<smartfire-component([^>]*?)attributes="([^"]*)"', t):
        n = re.search(r"name='([^']*)'", m.group(1)); n = n.group(1) if n else "?"
        if n in ("competitions---competition-main-menu", "competitions---search-bar"):
            d = json.loads(html.unescape(m.group(2)))
            s = json.dumps(d, ensure_ascii=False)
            print("##", c, n, len(s)); print("  keys", list(d.keys()))
            # compétitions de coupe ou de la ligue BFC / Haute-Saône
            for x in re.finditer(r'\{[^{}]*(?:[Cc]oupe|COUPE)[^{}]*\}', s): print("  C", x.group(0)[:400])
            print("  head", s[:1500])
    js = sorted(set(re.findall(r'https?://[^"\s\']*(?:api|json)[^"\s\']*', t)))[:20]; print("  api", js)
