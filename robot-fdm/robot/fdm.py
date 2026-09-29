"""Lecture d'une feuille de match électronique (FDME) FFHandball au format PDF.

Les stats sont rangées en colonnes (Buts, 7m, Tirs, Arrets, Av., 2', Dis) dont beaucoup
de cases sont vides : chaque chiffre est rattaché à la colonne dont l'en-tête est le plus
proche horizontalement. Résultat : score + liste des joueurs de chaque équipe.
"""
import re, io
import pdfplumber

COLS = {"Buts": "buts", "7m": "7m", "Tirs": "tirs", "Arrets": "arrets", "Av.": "av", "2'": "excl", "Dis": "dis"}
LICENCE = re.compile(r"^\d{13}$")
NUM = re.compile(r"^\d{1,3}$")


def _lines(words, tol=2.5):
    """Regroupe les mots par ligne (même hauteur)."""
    rows = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        for r in rows:
            if abs(r[0]["top"] - w["top"]) < tol:
                r.append(w); break
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w["x0"]) for r in sorted(rows, key=lambda r: r[0]["top"])]


def clean_name(s):
    s = re.sub(r"\(N[ée]\.?e?\s[^)]*\)", "", s)      # « (Né.e HUGOT) »
    return re.sub(r"\s+", " ", s).strip()


def parse_fdm(data):
    """data : contenu binaire du PDF. Renvoie dict(code, journee, score=(dom, ext), equipes=[{joueurs:[...]}, {...}])."""
    pdf = pdfplumber.open(io.BytesIO(data))
    teams, cols, cur = [], None, None
    head = {"code": None, "journee": None, "score": None}
    for pno, page in enumerate(pdf.pages):
        lines = _lines(page.extract_words())
        for ln in lines:
            txt = [w["text"] for w in ln]
            if pno == 0 and head["code"] is None and "Renc" in txt:
                head["code"] = txt[-1]
            if pno == 0 and head["journee"] is None and "Journée" in txt:
                j = txt[txt.index("Journée") + 1]
                if re.match(r"^J\d+$", j): head["journee"] = int(j[1:])
            if pno == 0 and head["score"] is None and "/" in txt:
                nums = [w for w in ln if NUM.match(w["text"]) and w["x0"] > 400]
                if len(nums) >= 2: head["score"] = (int(nums[-2]["text"]), int(nums[-1]["text"]))
            if "Licence" in txt and "Buts" in txt:          # en-tête d'une équipe
                cols = {COLS[w["text"]]: (w["x0"] + w["x1"]) / 2 for w in ln if w["text"] in COLS}
                lic_x = next(w for w in ln if w["text"] == "Licence")["x0"]
                cur = {"joueurs": []}; teams.append(cur); continue
            if cur is None: continue
            lic = [w for w in ln if LICENCE.match(w["text"])]
            if not lic or any(t.startswith("Officiel") for t in txt): continue
            lic = lic[0]
            num = [w for w in ln if NUM.match(w["text"]) and w["x1"] < lic["x0"] and w["x0"] < 115]
            name = clean_name(" ".join(w["text"] for w in ln if w["x0"] >= 110 and w["x1"] <= lic["x0"] - 2))
            p = {"nom": name, "licence": lic["text"], "numero": num[-1]["text"] if num else "",
                 "buts": 0, "tirs": 0, "excl": 0, "arrets": None, "7m": 0, "dis": False}
            for w in ln:
                if w["x0"] <= lic["x1"] + 25: continue        # licence + type de licence
                cx = (w["x0"] + w["x1"]) / 2
                k = min(cols, key=lambda c: abs(cols[c] - cx))
                if abs(cols[k] - cx) > 14: continue
                if NUM.match(w["text"]):
                    v = int(w["text"])
                    if k == "arrets": p["arrets"] = v
                    elif k in ("buts", "tirs", "excl", "7m"): p[k] = v
                elif k == "dis": p["dis"] = True
            cur["joueurs"].append(p)
    if len(teams) != 2:
        raise ValueError(f"format inattendu : {len(teams)} équipes trouvées")
    return {**head, "equipes": teams}


def controles(fdm):
    """Liste des incohérences (vide si tout va bien)."""
    pb = []
    if not fdm["score"]: return ["score introuvable"]
    for i, t in enumerate(fdm["equipes"]):
        b = sum(p["buts"] for p in t["joueurs"])
        if b != fdm["score"][i]:
            pb.append(f"équipe {i+1} : {b} buts sur la feuille pour un score de {fdm['score'][i]}")
        for p in t["joueurs"]:
            if p["buts"] > p["tirs"] and p["tirs"] > 0:
                pb.append(f"{p['nom']} : {p['buts']} buts pour {p['tirs']} tirs")
    return pb


TIME = re.compile(r"^(?:(\d{1,2}):)?(\d{1,3}):(\d{2})$")   # 24:18 ou 01:00:00


def parse_deroule(data):
    """Déroulé du match : liste [(secondes, score_dom, score_ext), ...] à chaque changement de score."""
    pdf = pdfplumber.open(io.BytesIO(data))
    sec = lambda m: int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    ev = []
    for page in pdf.pages:
        words = page.extract_words()
        if not any(w["text"] == "Déroulé" for w in words):
            continue
        for w in words:
            m = TIME.match(w["text"])
            if not m: continue
            line = sorted([x for x in words if abs(x["top"] - w["top"]) < 2.5 and w["x1"] < x["x0"] < w["x1"] + 90],
                          key=lambda x: x["x0"])
            toks = [x["text"] for x in line]
            if len(toks) >= 3 and toks[0].isdigit() and toks[1] == "-" and toks[2].isdigit():
                ev.append((sec(m), int(toks[0]), int(toks[2])))
            elif len(toks) >= 1 and re.match(r"^\d+-\d+$", toks[0]):
                a, b = toks[0].split("-"); ev.append((sec(m), int(a), int(b)))
    ev.sort()
    out, last = [], (0, 0)
    for t, h, a in ev:
        if (h, a) != last and h >= last[0] and a >= last[1]:
            out.append((t, h, a)); last = (h, a)
    return out
