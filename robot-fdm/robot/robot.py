"""Robot d'import des feuilles de match FFHandball vers le Google Sheets des stats.

Usage : python robot/robot.py robot/config_honneur.json
Variables d'environnement :
  ROBOT_MODE   controle (par défaut) : écrit seulement l'onglet _Import_Controle, ne touche à rien d'autre
               reel : remplit les onglets clubs (uniquement les journées encore vides)
  NOMS_OFFICIELS  1 pour réécrire les noms avec l'orthographe de la feuille de match
  GOOGLE_CREDENTIALS  contenu JSON de la clé du compte de service
"""
import os, sys, re, json, html, time, datetime, unicodedata, difflib
import requests
from fdm import parse_fdm, controles, parse_deroule

UA = {"User-Agent": "Mozilla/5.0 (stats PRHB, import hebdomadaire)"}
ROW_P, ROW_P_END = 7, 26        # joueurs
ROW_G, ROW_G_END = 33, 37       # gardiens
ROW_SCORE_ADV = 38              # buts encaissés saisis à la main
ROW_HEAD = 5                    # en-têtes « J1 vs ... »
PLACEHOLDER = "non detaille"
LIC_TAB, LOG_TAB, CTRL_TAB, MATCH_TAB = "_Licences", "_Robot_Journal", "_Import_Controle", "_Matchs"
MATCH_HEAD = ["J", "Domicile", "Extérieur", "Date", "Salle", "Adresse", "Lat", "Lng", "Equipement",
              "MT dom", "MT ext", "Deroule", "Buts 7m", "Rouges", "FDM", "Mise a jour"]


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"\(ne\.?e?\s[^)]*\)", "", s.lower())
    return re.sub(r"[^a-z]+", " ", s).strip()


def sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b: return 0.0
    r1 = difflib.SequenceMatcher(None, a, b).ratio()
    r2 = difflib.SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio()
    return max(r1, r2)


def split_np(s):
    """Sépare NOM (mots en majuscules) et Prénom. Renvoie (nom, prénom) normalisés, ou None."""
    s = re.sub(r"\(N[ée]\.?e?\s[^)]*\)", "", str(s or ""))
    toks = s.split()
    up = [t for t in toks if re.sub(r"[^A-Za-zÀ-ÿ]", "", t).isupper() and len(re.sub(r"[^A-Za-zÀ-ÿ]", "", t)) > 1]
    lo = [t for t in toks if t not in up]
    if not up or not lo: return None
    return norm(" ".join(up)), norm(" ".join(lo))


def sim_person(a, b):
    """Ressemblance entre deux noms de joueur (0 à 1), NOM et Prénom comparés séparément."""
    A, B = split_np(a), split_np(b)
    if not A or not B: return sim(a, b)
    r = lambda x, y: difflib.SequenceMatcher(None, x, y).ratio()
    na, nb = set(A[0].split()), set(B[0].split())
    s_nom = 1.0 if (na <= nb or nb <= na) else r(A[0], B[0])            # ANNEQUIN / ANNEQUIN-INGRASSIA
    pa, pb = A[1], B[1]
    s_pre = 0.95 if min(len(pa), len(pb)) >= 3 and (pa.startswith(pb) or pb.startswith(pa)) else r(pa, pb)   # Abdel / Abdelghani
    if pa == pb: s_pre = 1.0
    return 0.6 * s_nom + 0.4 * s_pre


def feuille_suspecte(team):
    """Tous les buts de l'équipe attribués à un seul joueur : erreur de saisie à la table de marque."""
    b = [p["buts"] for p in team["joueurs"]]
    return len(b) >= 5 and sum(b) >= 10 and max(b) == sum(b)


def col_letter(n):
    s = ""
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


# ---------------------------------------------------------------- site FFHandball
def fetch(url, binary=False):
    for essai in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 404: return None
            r.raise_for_status()
            return r.content if binary else r.text
        except requests.RequestException:
            if essai == 2: raise
            time.sleep(5)


def rencontres_journee(poule_url, j):
    page = fetch(f"{poule_url}journee-{j}/")
    if not page: return []
    for m in re.finditer(r'<smartfire-component[^>]*?attributes="([^"]*)"', page):
        raw = html.unescape(m.group(1))
        if '"rencontres"' not in raw: continue
        data = json.loads(raw)
        return [{"j": int(x.get("journeeNumero") or j), "dom": x["equipe1Libelle"], "ext": x["equipe2Libelle"],
                 "sd": x.get("equipe1Score"), "se": x.get("equipe2Score"), "code": x.get("fdmCode"),
                 "date": (x.get("date") or "")[:10], "datetime": (x.get("date") or "")[:16],
                 "rid": x.get("ext_rencontreId"), "eq": x.get("equipementId") or "",
                 "mtd": x.get("equipe1ScoreMT"), "mte": x.get("equipe2ScoreMT")} for x in data["rencontres"]]
    raise RuntimeError(f"journée {j} : données introuvables sur la page (le site a peut-être changé)")


def salle_rencontre(poule_url, rid):
    """Gymnase d'une rencontre (nom, adresse, coordonnées) depuis la page du match."""
    page = fetch(f"{poule_url}rencontre-{rid}/")
    if not page: return None
    for m in re.finditer(r'<smartfire-component[^>]*?attributes="([^"]*)"', page):
        raw = html.unescape(m.group(1))
        if '"equipement"' not in raw: continue
        e = json.loads(raw).get("equipement") or {}
        if not e: return None
        adr = ", ".join(x for x in [(e.get("rue") or "").strip(), " ".join(x for x in [(e.get("codePostal") or "").strip(), (e.get("ville") or "").strip()] if x)] if x)
        return {"salle": (e.get("libelle") or "").strip(), "adresse": adr, "lat": e.get("latitude") or "", "lng": e.get("longitude") or ""}
    return None


def fdm_url(code):
    return f"https://fdm.fdme.ffhandball.fr/{code[0]}/{code[1]}/{code[2]}/{code[3]}/{code}.pdf"


# ---------------------------------------------------------------- Google Sheets
class GBook:
    def __init__(self, sheet_id):
        import gspread
        from google.oauth2.service_account import Credentials
        info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        self.sh = gspread.authorize(creds).open_by_key(sheet_id)
        self._ws = {ws.title: ws for ws in self.sh.worksheets()}

    def tabs(self): return list(self._ws)

    def read(self, tab, rng="A1:BT40"):
        v = self._ws[tab].get(rng)
        return [row + [""] * (72 - len(row)) for row in v] + [[""] * 72 for _ in range(40 - len(v))]

    def read_all(self, tab):
        return self._ws[tab].get_all_values() if tab in self._ws else None

    def ensure(self, tab, header):
        if tab not in self._ws:
            ws = self.sh.add_worksheet(tab, rows=500, cols=max(12, len(header)))
            ws.update([header], "A1"); self._ws[tab] = ws

    def write(self, tab, cells):          # cells : liste de (ligne, colonne, valeur)
        if not cells: return
        data = [{"range": f"{col_letter(c)}{r}", "values": [[v]]} for r, c, v in cells]
        self._ws[tab].batch_update(data, value_input_option="USER_ENTERED")

    def append(self, tab, rows):
        if rows: self._ws[tab].append_rows(rows, value_input_option="USER_ENTERED")

    def replace(self, tab, rows, raw=False):
        ws = self._ws[tab]; ws.clear()
        ws.update([[str(x) if raw else x for x in r] for r in rows], "A1", value_input_option="RAW" if raw else "USER_ENTERED")


# ---------------------------------------------------------------- correspondance des joueurs
class Club:
    def __init__(self, tab, grid, licences):
        self.tab, self.g = tab, grid
        self.lic = {l: (t, r) for l, (tb, t, r) in licences.items() if tb == tab}

    def name(self, r): return str(self.g[r - 1][0]).strip()

    def block(self, j): return 7 + 3 * (j - 1)

    def head_ok(self, j):
        return re.match(rf"^\s*J{j}\b", str(self.g[ROW_HEAD - 1][self.block(j) - 1])) is not None

    def filled(self, j):
        c = self.block(j) - 1
        cells = [self.g[r - 1][c + k] for r in range(ROW_P, ROW_P_END + 1) for k in range(3)]
        cells += [self.g[r - 1][c] for r in range(ROW_G, ROW_G_END + 1)] + [self.g[ROW_SCORE_ADV - 1][c]]
        return any(str(x).strip() != "" for x in cells)

    def assign(self, kind, players):
        """Affecte chaque joueur de la feuille à une ligne : exacts d'abord, puis du plus ressemblant au moins ressemblant."""
        lo, hi = (ROW_P, ROW_P_END) if kind == "J" else (ROW_G, ROW_G_END)
        res, used = {}, set()
        others = {x[1] for l, x in self.lic.items() if x[0] == kind}
        for i, p in enumerate(players):                                     # 1. licence connue
            if p["licence"] in self.lic and self.lic[p["licence"]][0] == kind:
                r = self.lic[p["licence"]][1]
                if lo <= r <= hi and self.name(r) and r not in used:
                    res[i] = (r, "licence", 1.0); used.add(r)
        rows = [r for r in range(lo, hi + 1) if self.name(r) and norm(self.name(r)) != PLACEHOLDER]
        pairs = sorted(((sim_person(self.name(r), p["nom"]), i, r) for i, p in enumerate(players) if i not in res
                        for r in rows if r not in used and (r not in others or self.lic.get(p["licence"], (None, 0))[1] == r)), reverse=True)
        best_of = {}
        for sc, i, r in pairs: best_of.setdefault(i, []).append((sc, r))
        for sc, i, r in pairs:                                               # 2. du plus sûr au moins sûr
            if i in res or r in used: continue
            if sc >= 0.999:
                res[i] = (r, "exact" if norm(self.name(r)) == norm(players[i]["nom"]) else "proche", sc); used.add(r); continue
            alt = [x for x, rr in best_of[i] if rr != r and rr not in used]
            second = alt[0] if alt else 0
            if sc >= 0.85 and sc - second >= 0.08: res[i] = (r, "proche", sc); used.add(r)
            elif sc >= 0.60: res[i] = (r, "a_confirmer", sc); used.add(r)
        free = [r for r in range(lo, hi + 1) if not self.name(r)]           # 3. nouveaux joueurs
        for i, p in enumerate(players):
            if i not in res:
                res[i] = (free.pop(0), "nouveau", 0.0) if free else (None, "plus_de_place", 0.0)
        return res

    def resolve(self, kind, p, taken):
        """kind 'J' (joueur) ou 'G' (gardien). Renvoie (ligne, mode, score)."""
        lo, hi = (ROW_P, ROW_P_END) if kind == "J" else (ROW_G, ROW_G_END)
        if p["licence"] in self.lic and self.lic[p["licence"]][0] == kind:
            r = self.lic[p["licence"]][1]
            if lo <= r <= hi and self.name(r) and r not in taken: return r, "licence", 1.0
        cands = [(sim(self.name(r), p["nom"]), r) for r in range(lo, hi + 1)
                 if self.name(r) and norm(self.name(r)) != PLACEHOLDER and r not in taken
                 and r not in [x[1] for l, x in self.lic.items() if x[0] == kind and l != p["licence"]]]
        cands.sort(reverse=True)
        if cands:
            best, r = cands[0]; second = cands[1][0] if len(cands) > 1 else 0
            if best >= 0.999: return r, "exact", best
            if best >= 0.85 and best - second >= 0.08: return r, "proche", best
            if best >= 0.60: return r, "a_confirmer", best
        free = [r for r in range(lo, hi + 1) if not self.name(r) and r not in taken]
        return (free[0], "nouveau", 0.0) if free else (None, "plus_de_place", 0.0)


# ---------------------------------------------------------------- programme principal
def main(cfg_path):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    mode = os.environ.get("ROBOT_MODE", "controle").strip().lower()
    # rattrapage : comme reel, et en plus, pour les journées déjà saisies, met les noms à l'orthographe
    # officielle et ajoute les joueurs absents du fichier (sans toucher aux chiffres déjà saisis)
    ecrit = mode in ("reel", "rattrapage")

    noms_off = os.environ.get("NOMS_OFFICIELS", "0") == "1" or os.environ.get("ROBOT_MODE", "").strip().lower() == "rattrapage"
    book = BOOK_FACTORY(cfg["sheet_id"])
    manquants = [t for t in cfg["equipes"].values() if t not in book.tabs()]
    if manquants: raise SystemExit(f"Onglets introuvables : {manquants}. Onglets présents : {book.tabs()}")

    lic_rows = book.read_all(LIC_TAB) or []
    licences = {r[0]: (r[1], r[2], int(r[3])) for r in lic_rows[1:] if len(r) >= 4 and r[0] and str(r[3]).isdigit()}
    clubs = {t: Club(t, book.read(t), licences) for t in cfg["equipes"].values()}

    matchs = []
    for j in range(1, cfg["journees"] + 1):
        matchs += rencontres_journee(cfg["poule_url"], j)
    try:
        from zoneinfo import ZoneInfo
        ici = datetime.datetime.now(ZoneInfo("Europe/Paris")).replace(tzinfo=None)
    except Exception:
        ici = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    now = ici.strftime("%d/%m/%Y %H:%M")
    pdf_cache = {}
    # Feuilles de match déjà en ligne alors que le site n'affiche pas encore le score :
    # on lit le score sur la feuille, pour les matchs commencés depuis plus de 80 minutes.
    n_ant = 0
    for m in matchs:
        if str(m["sd"] or "").strip() != "" or not m.get("code") or not m.get("datetime"): continue
        try: debut = datetime.datetime.strptime(m["datetime"], "%Y-%m-%dT%H:%M")
        except ValueError: continue
        if not (debut + datetime.timedelta(minutes=80) <= ici <= debut + datetime.timedelta(days=30)): continue
        data = fetch(fdm_url(m["code"]), binary=True)
        if not data: continue
        try: f0 = parse_fdm(data)
        except Exception: continue
        if f0["score"] and sum(f0["score"]) > 0:
            m["sd"], m["se"], m["anticipe"] = str(f0["score"][0]), str(f0["score"][1]), True
            pdf_cache[m["code"]] = data; n_ant += 1
    joues = [m for m in matchs if str(m["sd"] or "").strip() != "" and str(m["se"] or "").strip() != ""]
    print(f"{len(joues)} matchs joués trouvés" + (f", dont {n_ant} lus sur la feuille avant la mise à jour du site" if n_ant else ""))
    journal, ctrl, new_lic = [], [], []
    ctrl_head = ["J", "Match", "Onglet", "Type", "Nom sur la feuille de match", "Ligne", "Nom dans le fichier",
                 "Correspondance", "Tirs / Arrêts", "Buts", "2 min", "Déjà saisi (Tirs / Buts / 2 min)", "Écart"]

    for m in joues:
        tabs = [cfg["equipes"].get(m["dom"]), cfg["equipes"].get(m["ext"])]
        label = f"J{m['j']} {m['dom']} {m['sd']}-{m['se']} {m['ext']}"
        if None in tabs:
            journal.append([now, m["j"], label, "ERREUR", "équipe absente de la configuration"]); continue
        todo = [t for t in tabs if not clubs[t].filled(m["j"])]
        if mode == "reel" and not todo: continue
        if not m["code"]:
            journal.append([now, m["j"], label, "EN ATTENTE", "pas encore de feuille de match"]); continue
        data = pdf_cache.get(m["code"]) or fetch(fdm_url(m["code"]), binary=True)
        if data: pdf_cache[m["code"]] = data
        if not data:
            journal.append([now, m["j"], label, "EN ATTENTE", f"feuille {m['code']} pas encore en ligne"]); continue
        try:
            f = parse_fdm(data)
        except Exception as e:
            journal.append([now, m["j"], label, "ERREUR", f"lecture de la feuille {m['code']} : {e}"]); continue
        non_detaille = f["score"] and sum(f["score"]) > 0 and all(sum(p["buts"] for p in t["joueurs"]) == 0 for t in f["equipes"])
        pb = [] if non_detaille else controles(f)
        if f["score"] != (int(m["sd"]), int(m["se"])):
            pb.append(f"score de la feuille {f['score']} différent du site {m['sd']}-{m['se']}")
        if f["journee"] and f["journee"] != m["j"]:
            pb.append(f"la feuille indique J{f['journee']}")
        if pb:
            journal.append([now, m["j"], label, "ERREUR", " ; ".join(pb)]); continue

        if non_detaille:
            for side, tab in enumerate(tabs):
                cl = clubs[tab]; j = m["j"]; c0 = cl.block(j)
                if cl.filled(j) or not cl.head_ok(j):
                    if not ecrit: journal.append([now, j, label, "NON DÉTAILLÉE", f"{tab} : feuille sans stats individuelles, journée déjà saisie"])
                    continue
                if not ecrit:
                    journal.append([now, j, label, "NON DÉTAILLÉE", f"{tab} : seul le score serait importé"]); continue
                rows = [r for r in range(ROW_P, ROW_P_END + 1) if norm(cl.name(r)) == PLACEHOLDER] or \
                       [r for r in range(ROW_P, ROW_P_END + 1) if not cl.name(r)]
                if not rows:
                    journal.append([now, j, label, "ERREUR", f"{tab} : pas de ligne libre pour « Non détaillé »"]); continue
                r = rows[0]
                cells = [(r, 1, "Non détaillé"), (r, c0 + 1, f["score"][side]), (ROW_SCORE_ADV, c0, f["score"][1 - side])]
                book.write(tab, cells)
                for rr, cc, v in cells: cl.g[rr - 1][cc - 1] = v
                journal.append([now, j, label, "IMPORTÉ", f"{tab} : score seul (feuille de match non détaillée)"])
            continue
        for side, (tab, team) in enumerate(zip(tabs, f["equipes"])):
            cl = clubs[tab]; j = m["j"]; c0 = cl.block(j)
            if not cl.head_ok(j):
                journal.append([now, j, label, "ERREUR", f"{tab} : l'en-tête de la colonne {col_letter(c0)}{ROW_HEAD} n'est pas J{j}"]); continue
            deja = cl.filled(j)
            if mode == "reel" and deja: continue
            adv = f["score"][1 - side]
            plan, douteux = [], []
            susp = feuille_suspecte(team)
            if susp and not deja:
                nom_s = max(team["joueurs"], key=lambda p: p["buts"])["nom"]
                journal.append([now, j, label, "FEUILLE SUSPECTE", f"{tab} : les {f['score'][side]} buts sont tous attribués à {nom_s} ; "
                                + ("équipe importée en non détaillé (score seul)" if ecrit else "l'équipe serait importée en non détaillé")])
            groupes = {"G": [p for p in team["joueurs"] if p["arrets"] is not None],
                       "J": [] if susp else [p for p in team["joueurs"] if p["arrets"] is None or p["tirs"] or p["buts"]]}
            for k, ps in groupes.items():
                aff = cl.assign(k, ps)
                for i, p in enumerate(ps):
                    r, how, sc = aff[i]
                    if how == "a_confirmer": douteux.append(f"{p['nom']} ressemble à « {cl.name(r)} » (ligne {r}) sans certitude")
                    if how == "plus_de_place": douteux.append(f"{p['nom']} : plus de ligne libre")
                    plan.append((k, p, r, how, sc))
            # onglet de contrôle
            for k, p, r, how, sc in plan:
                cur = ""; ecart = ""
                if r:
                    row = cl.g[r - 1]
                    if k == "J":
                        cur_v = [row[c0 - 1 + i] for i in range(3)]; new_v = [p["tirs"], p["buts"], p["excl"]]
                    else:
                        cur_v = [row[c0 - 1]]; new_v = [p["arrets"]]
                    if any(str(x).strip() for x in cur_v):
                        cur = " / ".join(str(x) for x in cur_v)
                        n0 = lambda x: str(x).strip() or "0"          # case vide = 0
                        ecart = "" if [n0(x) for x in cur_v] == [str(x) for x in new_v] else "ÉCART"
                ctrl.append([j, label, tab, "Gardien" if k == "G" else "Joueur", p["nom"], r or "",
                             cl.name(r) if r else "", f"{how} ({round(sc*100)} %)" if how in ("proche", "a_confirmer") else how,
                             p["arrets"] if k == "G" else p["tirs"], "" if k == "G" else p["buts"],
                             "" if k == "G" else p["excl"], cur, ecart])
            if not ecrit: continue
            if douteux:
                journal.append([now, j, label, "À CONFIRMER", f"{tab} {'non importé' if not deja else 'non corrigé'} : " + ", ".join(douteux)]); continue
            cells, renommes = [], []
            for k, p, r, how, sc in plan:
                if how == "nouveau" or (noms_off and norm(cl.name(r)) != norm(p["nom"])):   # accents et majuscules conservés
                    cells.append((r, 1, p["nom"]))
                    if how != "nouveau": renommes.append(f"{cl.name(r)} → {p['nom']}")
                if not deja or how == "nouveau":          # journée déjà saisie : seuls les joueurs absents reçoivent leurs chiffres
                    if k == "J": cells += [(r, c0, p["tirs"]), (r, c0 + 1, p["buts"]), (r, c0 + 2, p["excl"])]
                    else: cells.append((r, c0, p["arrets"]))
                if p["licence"] not in licences or licences[p["licence"]][:2] != (tab, k):
                    licences[p["licence"]] = (tab, k, r); cl.lic[p["licence"]] = (k, r)
                    new_lic.append([p["licence"], tab, k, r, p["nom"]])
            if susp and not deja:
                libres = [r for r in range(ROW_P, ROW_P_END + 1) if norm(cl.name(r)) == PLACEHOLDER] or \
                         [r for r in range(ROW_P, ROW_P_END + 1) if not cl.name(r)]
                if libres: cells += [(libres[0], 1, "Non détaillé"), (libres[0], c0 + 1, f["score"][side])]
            if not deja: cells.append((ROW_SCORE_ADV, c0, adv))
            if cells: book.write(tab, cells)
            for rr, cc, v in cells:          # mise à jour de la copie locale
                cl.g[rr - 1][cc - 1] = v
            nouveaux = [p["nom"] for k, p, r, how, sc in plan if how == "nouveau"]
            if deja and not nouveaux and not renommes: continue
            det = (f"{tab} : {len(plan)} lignes" if not deja else f"{tab} (journée déjà saisie)") + \
                  (" (score lu sur la feuille, site pas encore à jour)" if m.get("anticipe") else "") + \
                  (f", ajoutés : {', '.join(nouveaux)}" if nouveaux else "") + (f", renommés : {', '.join(renommes)}" if renommes else "")
            journal.append([now, j, label, "IMPORTÉ" if not deja else "CORRIGÉ", det])

    if ecrit:
        try:
            maj_matchs(book, cfg, matchs, pdf_cache, now, journal)
        except Exception as e:
            journal.append([now, "", "", "ERREUR", f"onglet {MATCH_TAB} : {e}"])
        book.ensure(LIC_TAB, ["Licence", "Onglet", "Type", "Ligne", "Nom"]); book.append(LIC_TAB, new_lic)
    else:
        book.ensure(CTRL_TAB, ctrl_head); book.replace(CTRL_TAB, [ctrl_head] + ctrl)
    book.ensure(LOG_TAB, ["Date", "J", "Match", "Statut", "Détail"])
    if not ecrit:
        n_ecarts = sum(1 for l in ctrl if l[-1] == "ÉCART")
        journal.append([now, "", "", "CONTRÔLE", f"{len(ctrl)} lignes dans {CTRL_TAB}, dont {n_ecarts} écart(s)"])
    if not journal: journal = [[now, "", "", "RIEN À FAIRE" if ecrit else "CONTRÔLE", f"mode {mode}, aucune nouvelle feuille" if ecrit else f"{len(ctrl)} lignes dans {CTRL_TAB}"]]
    book.append(LOG_TAB, journal)
    for l in journal: print(" | ".join(str(x) for x in l))
    try:   # trace dans le dépôt GitHub (garde aussi le robot actif)
        with open(os.path.join(os.path.dirname(__file__), "derniere_execution_" + os.path.splitext(os.path.basename(cfg_path))[0].replace("config_", "") + ".txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(" | ".join(str(x) for x in l) for l in journal) + "\n")
    except OSError: pass
    erreurs = [l for l in journal if l[3] in ("ERREUR", "À CONFIRMER")]
    return 1 if erreurs else 0


def maj_matchs(book, cfg, matchs, pdf_cache, now, journal):
    """Onglet _Matchs : date/heure, salle, mi-temps, déroulé (momentum), buts sur 7 m, cartons rouges."""
    old = book.read_all(MATCH_TAB) or []
    head = old[0] if old else MATCH_HEAD
    rows = {}
    for r in old[1:]:
        d = dict(zip(head, r + [""] * (len(head) - len(r))))
        rows[(str(d["J"]), d["Domicile"], d["Extérieur"])] = d
    salles = {d["Equipement"]: d for d in rows.values() if d.get("Equipement") and d.get("Salle")}
    n_sal = n_der = 0
    out = []
    for m in matchs:
        key = (str(m["j"]), m["dom"], m["ext"])
        d = {k: "" for k in MATCH_HEAD}; d.update(rows.get(key, {}))
        d["J"], d["Domicile"], d["Extérieur"] = m["j"], m["dom"], m["ext"]
        if m.get("datetime"): d["Date"] = m["datetime"]
        eq = str(m.get("eq") or "")
        if eq and (eq != str(d.get("Equipement")) or not d.get("Salle")):
            if eq in salles:
                s = salles[eq]; d.update({k: s[k] for k in ("Salle", "Adresse", "Lat", "Lng")})
            elif m.get("rid") and n_sal < 40:
                s = salle_rencontre(cfg["poule_url"], m["rid"]); n_sal += 1
                if s:
                    d.update({"Salle": s["salle"], "Adresse": s["adresse"], "Lat": s["lat"], "Lng": s["lng"]})
                    salles[eq] = {"Salle": s["salle"], "Adresse": s["adresse"], "Lat": s["lat"], "Lng": s["lng"]}
            d["Equipement"] = eq
        joue = str(m["sd"] or "").strip() != "" and str(m["se"] or "").strip() != ""
        if joue:
            if m.get("mtd") not in (None, ""): d["MT dom"], d["MT ext"] = m["mtd"], m["mte"]
            if m.get("code") and (not d.get("Deroule") or d.get("FDM") != m["code"]):
                data = pdf_cache.get(m["code"]) or fetch(fdm_url(m["code"]), binary=True)
                if data:
                    try:
                        f = parse_fdm(data); ev = parse_deroule(data)
                        if sum(p["buts"] for t in f["equipes"] for p in t["joueurs"]) == 0 and sum(f["score"] or (0, 0)) > 0:
                            d["Deroule"] = "ND"                     # feuille non détaillée
                        else:
                            d["Deroule"] = " ".join(f"{t}:{h}-{a}" for t, h, a in ev) or "ND"
                            cote = ("D", "E")
                            d["Buts 7m"] = "|".join(f"{cote[i]}:{p['nom']}={p['7m']}" for i, t in enumerate(f["equipes"]) if not feuille_suspecte(t) for p in t["joueurs"] if p["7m"])
                            d["Rouges"] = "|".join(f"{cote[i]}:{p['nom']}" for i, t in enumerate(f["equipes"]) for p in t["joueurs"] if p["dis"])
                        d["FDM"] = m["code"]; d["Mise a jour"] = now; n_der += 1
                    except Exception as e:
                        journal.append([now, m["j"], f"J{m['j']} {m['dom']} - {m['ext']}", "ERREUR", f"déroulé illisible : {e}"])
        out.append([d.get(k, "") for k in MATCH_HEAD])
    book.ensure(MATCH_TAB, MATCH_HEAD)
    book.replace(MATCH_TAB, [MATCH_HEAD] + out, raw=True)
    if n_der or n_sal:
        journal.append([now, "", "", "MATCHS", f"{MATCH_TAB} : {n_der} déroulé(s) ajouté(s), {n_sal} salle(s) relevée(s)"])


BOOK_FACTORY = GBook
if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "robot/config_honneur.json"))
