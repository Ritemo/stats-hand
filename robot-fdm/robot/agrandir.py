"""Agrandissement des onglets clubs : 30 lignes joueurs (au lieu de 20) et 8 lignes gardiens (au lieu de 5).

Lancé par le workflow en mode « agrandir-test » (rien n'est écrit, le journal décrit ce qui serait fait)
puis « agrandir ». Tout part en une seule requête Google Sheets, appliquée en entier ou pas du tout :
 1. onglets de calcul : les numéros de ligne écrits en texte dans les formules INDIRECT ("'!R27C", "G38:BR38"...)
    sont décalés, et les blocs de 20 lignes de _Data_Joueurs_J passent à 30 ;
 2. onglets clubs : 10 lignes insérées avant la ligne 26 (« Non détaillé »), 3 lignes gardiens avant la dernière ;
    les formules des totaux sont recopiées dans les nouvelles lignes (Google Sheets décale tout seul les autres
    références, ce qui garde les totaux, le comparatif et les classements justes) ;
 3. _Data_Joueurs (+10 lignes par club), _Data_Gardiens (+3 par club), _Data_Joueurs_J (prolongé) ;
 4. _Licences : numéros de ligne des gardiens décalés.
Tous les chiffres calculés (comparatif, classements, onglets _Data) sont relevés avant et après :
s'ils ont bougé, l'opération est défaite automatiquement.
"""
import re, time
from collections import Counter

ADD_P, ADD_G = 10, 3              # lignes ajoutées : joueurs, gardiens
OLD_P1, OLD_G1 = 26, 37           # dernière ligne joueur et dernière ligne gardien avant agrandissement
NEW_BLOC = 20 + ADD_P             # lignes par club dans _Data_Joueurs_J
ROBOT_TABS = {"_Robot_Journal", "_Import_Controle", "_Licences", "_Matchs", "Calendrier"}

LIT = re.compile(r'"((?:[^"]|"")*)"')
R1C1 = re.compile(r'(?<![A-Za-z])R(\d+)C')
A1 = re.compile(r'(?<![A-Za-z])([A-Z]{1,3})(\d+)(?!\d)')
RX_MOD = r'(MOD\(\s*(?:ROW|LIGNE)\(\)\s*-\s*2\s*[,;]\s*)20(\s*\))'
RX_INT = r'(\(\s*(?:ROW|LIGNE)\(\)\s*-\s*2\s*\)\s*/\s*)20(\s*\))'
RX_MOD_INV = RX_MOD.replace(")20(", ")30(")
RX_INT_INV = RX_INT.replace(")20(", ")30(")
REF = re.compile(r"^='?(.+?)'?!\$?A\$?(\d+)$")


def f(r):
    """Ancien numéro de ligne d'un onglet club -> nouveau numéro."""
    return r if r < OLD_P1 else (r + ADD_P if r < OLD_G1 else r + ADD_P + ADD_G)


def map_literal(s):
    """Texte entre guillemets d'une formule INDIRECT : décale les numéros de ligne qu'il contient."""
    if not s.startswith((":", "!", "'!")): return s                 # "'!R27C", ":R37C", "'!G38:BR38"...
    if R1C1.search(s): return R1C1.sub(lambda m: f"R{f(int(m.group(1)))}C", s)
    return A1.sub(lambda m: f"{m.group(1)}{f(int(m.group(2)))}", s)


def literal_pairs(formulas):
    """formulas : textes des formules d'un onglet. Renvoie [(ancien, nouveau, occurrences)] (guillemets compris),
    dans un ordre où aucun remplacement ne peut en retoucher un autre."""
    cnt = Counter()
    for t in formulas:
        if "INDIRECT" not in t.upper(): continue
        for m in LIT.finditer(t):
            new = map_literal(m.group(1))
            if new != m.group(1): cnt[(f'"{m.group(1)}"', f'"{new}"')] += 1
    key = lambda p: -max(int(x) for x in re.findall(r"\d+", p[0]))
    pairs = sorted(((a, b, n) for (a, b), n in cnt.items()), key=key)
    for i, (a, b, n) in enumerate(pairs):
        for a2, b2, n2 in pairs[i + 1:]:
            if a2 in b: raise RuntimeError(f"remplacements en conflit : {a} -> {b} puis {a2}")
    return pairs


def grid(values):
    """valeurs d'une plage -> dict {(ligne, colonne): texte} (1-based)."""
    return {(i + 1, j + 1): v for i, row in enumerate(values or []) for j, v in enumerate(row) if v not in ("", None)}


def plan(meta, formules, clubs, licences):
    """Calcule tout ce qui sera fait. meta : {onglet: (sheetId, nb_lignes)} ; formules : {onglet: grid FORMULA} ;
    clubs : onglets clubs ; licences : lignes de _Licences. Renvoie (plan, journal) ou lève une erreur."""
    P = {"fr": [], "ins": [], "data": {}, "lic": [], "notes": []}
    for t in clubs:
        g = formules[t]
        a = lambda r: str(g.get((r, 1), "")).strip().upper()
        if a(37) == "TOTAL ÉQUIPE" and a(27) != "TOTAL ÉQUIPE":
            raise RuntimeError("les onglets clubs sont déjà agrandis")
        if not (a(27) == "TOTAL ÉQUIPE" and a(31).startswith("GARDIEN") and a(38).startswith("BUTS CONC")):
            raise RuntimeError(f"onglet {t} : disposition inattendue (lignes 27, 31, 38)")
        if any("INDIRECT" in str(v).upper() for v in g.values()):
            raise RuntimeError(f"onglet {t} : formule INDIRECT inattendue dans un onglet club")
    autres = [t for t in formules if t not in clubs and t not in ROBOT_TABS]
    # 1. textes des formules INDIRECT, blocs de 20 lignes
    for t in autres:
        txt = [str(v) for v in formules[t].values() if str(v).startswith("=")]
        pairs = literal_pairs(txt)
        for a, b, n in pairs: P["fr"].append((t, a, b, n, False))
        n_mod = sum(len(re.findall(RX_MOD, x)) for x in txt); n_int = sum(len(re.findall(RX_INT, x)) for x in txt)
        if n_mod or n_int:
            if t != "_Data_Joueurs_J": raise RuntimeError(f"onglet {t} : blocs de 20 lignes inattendus")
            P["fr"].append((t, RX_MOD, r"$130$2", n_mod, True))
            P["fr"].append((t, RX_INT, r"$130$2", n_int, True))
        if pairs or n_mod or n_int:
            P["notes"].append(f"{t} : {sum(n for *_, n in pairs)} texte(s) de ligne à décaler" +
                              (f", {n_mod + n_int} bloc(s) de 20 lignes à passer à 30" if n_mod or n_int else "") +
                              (f" (ex. {pairs[0][0]} -> {pairs[0][1]})" if pairs else ""))
    # 2. onglets clubs
    for t in clubs: P["ins"].append(meta[t][0])
    # 3. _Data_Joueurs, _Data_Gardiens : un bloc de lignes par club
    for t, src_ref, last_ref, add in (("_Data_Joueurs", 25, 26, ADD_P), ("_Data_Gardiens", 36, 37, ADD_G)):
        if t not in formules: raise RuntimeError(f"onglet {t} introuvable")
        pos = {}
        for (r, c), v in formules[t].items():
            m = REF.match(str(v)) if c == 2 else None
            if m: pos[(m.group(1), int(m.group(2)))] = r
        blocs = []
        for club in clubs:
            L, S = pos.get((club, last_ref)), pos.get((club, src_ref))
            if not L or S != L - 1: raise RuntimeError(f"{t} : bloc de {club} introuvable ou dans un ordre inattendu")
            blocs.append(L)
        P["data"][t] = (meta[t][0], sorted(blocs, reverse=True), add)
        P["notes"].append(f"{t} : {len(blocs)} blocs de clubs trouvés, +{add} lignes chacun")
    # _Data_Joueurs_J : blocs de 20 lignes repérés par la formule
    t = "_Data_Joueurs_J"
    if t in formules:
        rows = [r for (r, c), v in formules[t].items() if c == 2 and str(v).startswith("=")]
        n = max(rows) if rows else 0
        if n != 1 + 20 * len(clubs): raise RuntimeError(f"{t} : {n} lignes au lieu de {1 + 20 * len(clubs)}")
        anchors = sorted(c for (r, c), v in formules[t].items() if r == n and str(v).startswith("="))
        P["data"][t] = (meta[t][0], n, 1 + NEW_BLOC * len(clubs), anchors, meta[t][1])
        P["notes"].append(f"{t} : prolongé de la ligne {n} à la ligne {1 + NEW_BLOC * len(clubs)}")
    # 4. _Licences
    for i, row in enumerate(licences[1:], start=2):
        if len(row) >= 4 and row[1] in clubs and re.fullmatch(r"\d+(\.0+)?", str(row[3]).strip()):
            old = int(float(str(row[3]).strip()))
            if f(old) != old: P["lic"].append((i, old, f(old)))
    P["notes"].append(f"_Licences : {len(P['lic'])} numéro(s) de ligne de gardien à décaler")
    return P


def requests(P, meta, inverse=False):
    """Requêtes Google Sheets de l'agrandissement (ou de son annulation)."""
    R = []
    fr = lambda sid, a, b, rx: {"findReplace": {"find": a, "replacement": b, "sheetId": sid, "includeFormulas": True,
                                               "matchCase": True, "searchByRegex": rx}}
    if not inverse:
        for t, a, b, n, rx in P["fr"]:
            if n: R.append(fr(meta[t][0], a, b, rx))
        for sid in P["ins"]:
            R.append({"insertDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": OLD_P1 - 1,
                                                    "endIndex": OLD_P1 - 1 + ADD_P}, "inheritFromBefore": True}})
            g1 = OLD_G1 + ADD_P                                   # ancienne ligne 37 après le premier ajout
            R.append({"insertDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": g1 - 1,
                                                    "endIndex": g1 - 1 + ADD_G}, "inheritFromBefore": True}})
            R.append(paste(sid, OLD_P1 - 2, OLD_P1 - 1, OLD_P1 - 1 + ADD_P, 1, 6, "PASTE_FORMULA"))   # B:F de la ligne 25
            R.append(paste(sid, g1 - 2, g1 - 1, g1 - 1 + ADD_G, 1, 3, "PASTE_FORMULA"))               # B:C du gardien du dessus
        for t in ("_Data_Joueurs", "_Data_Gardiens"):
            sid, blocs, add = P["data"][t]
            for L in blocs:                                       # du bas vers le haut
                R.append({"insertDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": L - 1,
                                                        "endIndex": L - 1 + add}, "inheritFromBefore": True}})
                R.append(paste(sid, L - 2, L - 1, L - 1 + add, 0, 26, "PASTE_NORMAL"))
        if "_Data_Joueurs_J" in P["data"]:
            sid, n, n2, anchors, nrows = P["data"]["_Data_Joueurs_J"]
            if nrows < n2:
                R.append({"appendDimension": {"sheetId": sid, "dimension": "ROWS", "length": n2 - nrows}})
            for c in anchors:
                R.append(paste(sid, n - 1, n, n2, c - 1, c, "PASTE_FORMULA"))
        lic_vals = [(i, new) for i, old, new in P["lic"]]
    else:
        if "_Data_Joueurs_J" in P["data"]:
            sid, n, n2, anchors, nrows = P["data"]["_Data_Joueurs_J"]
            if nrows < n2:
                R.append({"deleteDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": nrows, "endIndex": n2}}})
            else:
                for c in anchors:
                    R.append({"updateCells": {"range": {"sheetId": sid, "startRowIndex": n, "endRowIndex": n2,
                                                        "startColumnIndex": c - 1, "endColumnIndex": c}, "fields": "userEnteredValue"}})
        for t in ("_Data_Gardiens", "_Data_Joueurs"):
            sid, blocs, add = P["data"][t]
            for L in blocs:                                       # même ordre (du bas vers le haut)
                above = sum(1 for x in blocs if x < L)
                start = L - 1 + add * above
                R.append({"deleteDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": start, "endIndex": start + add}}})
        for sid in P["ins"]:
            g1 = OLD_G1 + ADD_P
            R.append({"deleteDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": g1 - 1, "endIndex": g1 - 1 + ADD_G}}})
            R.append({"deleteDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": OLD_P1 - 1, "endIndex": OLD_P1 - 1 + ADD_P}}})
        for t, a, b, n, rx in reversed(P["fr"]):
            if not n: continue
            if rx: R.append(fr(meta[t][0], RX_MOD_INV if a == RX_MOD else RX_INT_INV, r"$120$2", True))
            else: R.append(fr(meta[t][0], b, a, False))
        lic_vals = [(i, old) for i, old, new in P["lic"]]
    sid_lic = meta.get("_Licences", (None,))[0]
    for i, v in lic_vals:
        R.append({"updateCells": {"range": {"sheetId": sid_lic, "startRowIndex": i - 1, "endRowIndex": i,
                                            "startColumnIndex": 3, "endColumnIndex": 4},
                                  "rows": [{"values": [{"userEnteredValue": {"numberValue": v}}]}], "fields": "userEnteredValue"}})
    return R


def paste(sid, src, dst0, dst1, c0, c1, kind):
    """Copie la ligne src sur les lignes dst0 à dst1-1, colonnes c0 à c1-1 (tous les indices partent de 0)."""
    s = {"sheetId": sid, "startRowIndex": src, "endRowIndex": src + 1, "startColumnIndex": c0, "endColumnIndex": c1}
    d = {"sheetId": sid, "startRowIndex": dst0, "endRowIndex": dst1, "startColumnIndex": c0, "endColumnIndex": c1}
    return {"copyPaste": {"source": s, "destination": d, "pasteType": kind, "pasteOrientation": "NORMAL"}}


SNAP_FULL = ("Comparatif Clubs", "Classement général", "Classement Général", "_Data_Journees", "Classement Buteurs", "Classement Gardiens")
SNAP_SET = {"_Data_Joueurs": 6, "_Data_Gardiens": 4, "_Data_Joueurs_J": 99}


def snapshot(sh, tabs):
    """Chiffres calculés à comparer avant / après."""
    pris = [t for t in SNAP_FULL if t in tabs] + [t for t in SNAP_SET if t in tabs]
    vr = sh.values_batch_get([f"'{t}'" for t in pris], params={"valueRenderOption": "FORMATTED_VALUE"})["valueRanges"]
    out = {}
    for t, v in zip(pris, vr):
        rows = v.get("values", [])
        if t in SNAP_SET:
            k = SNAP_SET[t]
            out[t] = Counter(tuple(r[:k]) for r in rows[1:] if len(r) > 1 and str(r[1]).strip() not in ("", "0"))
        else:                                                    # colonne I : clés de tri qui dépendent du numéro de ligne
            skip = 8 if t.startswith("Classement Bu") or t.startswith("Classement Ga") else None
            out[t] = [tuple(x for j, x in enumerate(r) if j != skip) for r in rows]
    return out


def diff(a, b):
    return [t for t in a if a[t] != b.get(t)]


def run(sh, cfg, test, now):
    """Renvoie (journal, code de retour)."""
    J = lambda statut, txt: [now, "", "", statut, txt]
    journal = []
    clubs = list(dict.fromkeys(cfg["equipes"].values()))
    md = sh.fetch_sheet_metadata()
    meta = {s["properties"]["title"]: (s["properties"]["sheetId"], s["properties"]["gridProperties"]["rowCount"]) for s in md["sheets"]}
    tabs = [t for t in meta if t not in ROBOT_TABS or t == "_Licences"]
    vr = sh.values_batch_get([f"'{t}'" for t in tabs], params={"valueRenderOption": "FORMULA"})["valueRanges"]
    formules = {t: grid(v.get("values")) for t, v in zip(tabs, vr)}
    lic = sh.values_batch_get(["'_Licences'"], params={"valueRenderOption": "UNFORMATTED_VALUE"})["valueRanges"][0].get("values", []) \
        if "_Licences" in meta else []
    formules.pop("_Licences", None)
    try:
        P = plan(meta, formules, clubs, lic)
    except RuntimeError as e:
        return [J("ERREUR" if "déjà" not in str(e) else "RIEN À FAIRE", f"agrandissement : {e}")], (0 if "déjà" in str(e) else 1)
    journal += [J("AGRANDIR (essai)" if test else "AGRANDIR", x) for x in P["notes"]]
    reqs = requests(P, meta)
    if test:
        journal.append(J("AGRANDIR (essai)", f"{len(clubs)} onglets clubs : 30 lignes joueurs et 8 lignes gardiens au lieu de 20 et 5 ; "
                                              f"{len(reqs)} opérations prêtes, rien n'a été modifié"))
        return journal, 0
    avant = snapshot(sh, meta)
    rep = sh.batch_update({"requests": reqs})["replies"]
    n_fr = [r.get("findReplace", {}).get("occurrencesChanged", 0) for r, q in zip(rep, reqs) if "findReplace" in q]
    attendu = [n for t, a, b, n, rx in P["fr"] if n]
    pb = [] if n_fr == attendu else [f"remplacements dans les formules : {sum(n_fr)} au lieu de {sum(attendu)}"]
    for essai in range(4):
        time.sleep(4)
        apres = snapshot(sh, {t: 1 for t in meta})
        d = diff(avant, apres)
        if not d: break
    if d: pb.append("chiffres modifiés dans : " + ", ".join(d))
    if pb:
        sh.batch_update({"requests": requests(P, meta, inverse=True)})
        time.sleep(4)
        d2 = diff(avant, snapshot(sh, {t: 1 for t in meta}))
        journal.append(J("ERREUR", "agrandissement annulé (" + " ; ".join(pb) + ")" +
                         (", tout a été remis comme avant" if not d2 else
                          f" ; ATTENTION, écarts restants dans {', '.join(d2)} : restaurer la version d'avant via Fichier > Historique des versions")))
        return journal, 1
    journal.append(J("AGRANDI", f"{len(clubs)} onglets clubs : 30 lignes joueurs (7 à 36) et 8 lignes gardiens ; "
                                f"tous les chiffres calculés sont identiques à avant"))
    return journal, 0
