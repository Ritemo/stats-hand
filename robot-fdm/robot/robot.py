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
from fdm import parse_fdm, controles

UA = {"User-Agent": "Mozilla/5.0 (stats PRHB, import hebdomadaire)"}
ROW_P, ROW_P_END = 7, 26        # joueurs
ROW_G, ROW_G_END = 33, 37       # gardiens
ROW_SCORE_ADV = 38              # buts encaissés saisis à la main
ROW_HEAD = 5                    # en-têtes « J1 vs ... »
PLACEHOLDER = "non detaille"
LIC_TAB, LOG_TAB, CTRL_TAB = "_Licences", "_Robot_Journal", "_Import_Controle"


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
                 "date": (x.get("date") or "")[:10]} for x in data["rencontres"]]
    raise RuntimeError(f"journée {j} : données introuvables sur la page (le site a peut-être changé)")


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

    def replace(self, tab, rows):
        ws = self._ws[tab]; ws.clear(); ws.update(rows, "A1", value_input_option="USER_ENTERED")


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
    noms_off = os.environ.get("NOMS_OFFICIELS", "0") == "1"
    book = BOOK_FACTORY(cfg["sheet_id"])
    manquants = [t for t in cfg["equipes"].values() if t not in book.tabs()]
    if manquants: raise SystemExit(f"Onglets introuvables : {manquants}. Onglets présents : {book.tabs()}")

    lic_rows = book.read_all(LIC_TAB) or []
    licences = {r[0]: (r[1], r[2], int(r[3])) for r in lic_rows[1:] if len(r) >= 4 and r[0] and str(r[3]).isdigit()}
    clubs = {t: Club(t, book.read(t), licences) for t in cfg["equipes"].values()}

    matchs = []
    for j in range(1, cfg["journees"] + 1):
        matchs += rencontres_journee(cfg["poule_url"], j)
    joues = [m for m in matchs if str(m["sd"] or "").strip() != "" and str(m["se"] or "").strip() != ""]
    print(f"{len(joues)} matchs joués trouvés sur le site")

    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
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
        data = fetch(fdm_url(m["code"]), binary=True)
        if not data:
            journal.append([now, m["j"], label, "EN ATTENTE", f"feuille {m['code']} pas encore en ligne"]); continue
        try:
            f = parse_fdm(data)
        except Exception as e:
            journal.append([now, m["j"], label, "ERREUR", f"lecture de la feuille {m['code']} : {e}"]); continue
        pb = controles(f)
        if f["score"] != (int(m["sd"]), int(m["se"])):
            pb.append(f"score de la feuille {f['score']} différent du site {m['sd']}-{m['se']}")
        if f["journee"] and f["journee"] != m["j"]:
            pb.append(f"la feuille indique J{f['journee']}")
        if pb:
            journal.append([now, m["j"], label, "ERREUR", " ; ".join(pb)]); continue

        for side, (tab, team) in enumerate(zip(tabs, f["equipes"])):
            cl = clubs[tab]; j = m["j"]; c0 = cl.block(j)
            if not cl.head_ok(j):
                journal.append([now, j, label, "ERREUR", f"{tab} : l'en-tête de la colonne {col_letter(c0)}{ROW_HEAD} n'est pas J{j}"]); continue
            deja = cl.filled(j)
            if mode == "reel" and deja: continue
            adv = f["score"][1 - side]
            plan, taken, douteux = [], {"J": set(), "G": set()}, []
            for p in team["joueurs"]:
                kinds = []
                if p["arrets"] is not None: kinds.append("G")
                if p["arrets"] is None or p["tirs"] or p["buts"]: kinds.append("J")
                for k in kinds:
                    r, how, sc = cl.resolve(k, p, taken[k])
                    if r: taken[k].add(r)
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
                        ecart = "" if [str(x).strip() for x in cur_v] == [str(x) for x in new_v] else "ÉCART"
                ctrl.append([j, label, tab, "Gardien" if k == "G" else "Joueur", p["nom"], r or "",
                             cl.name(r) if r else "", f"{how} ({round(sc*100)} %)" if how in ("proche", "a_confirmer") else how,
                             p["arrets"] if k == "G" else p["tirs"], "" if k == "G" else p["buts"],
                             "" if k == "G" else p["excl"], cur, ecart])
            if mode != "reel": continue
            if douteux:
                journal.append([now, j, label, "À CONFIRMER", f"{tab} non importé : " + ", ".join(douteux)]); continue
            cells = []
            for k, p, r, how, sc in plan:
                if how == "nouveau" or (noms_off and cl.name(r) != p["nom"]):
                    cells.append((r, 1, p["nom"]))
                if k == "J": cells += [(r, c0, p["tirs"]), (r, c0 + 1, p["buts"]), (r, c0 + 2, p["excl"])]
                else: cells.append((r, c0, p["arrets"]))
                if p["licence"] not in licences or licences[p["licence"]][:2] != (tab, k):
                    licences[p["licence"]] = (tab, k, r); new_lic.append([p["licence"], tab, k, r, p["nom"]])
            cells.append((ROW_SCORE_ADV, c0, adv))
            book.write(tab, cells)
            for rr, cc, v in cells:          # mise à jour de la copie locale
                cl.g[rr - 1][cc - 1] = v
            nouveaux = [p["nom"] for k, p, r, how, sc in plan if how == "nouveau"]
            journal.append([now, j, label, "IMPORTÉ", f"{tab} : {len(plan)} lignes" + (f", nouveaux : {', '.join(nouveaux)}" if nouveaux else "")])

    if mode == "reel":
        book.ensure(LIC_TAB, ["Licence", "Onglet", "Type", "Ligne", "Nom"]); book.append(LIC_TAB, new_lic)
    else:
        book.ensure(CTRL_TAB, ctrl_head); book.replace(CTRL_TAB, [ctrl_head] + ctrl)
    book.ensure(LOG_TAB, ["Date", "J", "Match", "Statut", "Détail"])
    if not journal: journal = [[now, "", "", "RIEN À FAIRE" if mode == "reel" else "CONTRÔLE", f"mode {mode}, aucune nouvelle feuille" if mode == "reel" else f"{len(ctrl)} lignes dans {CTRL_TAB}"]]
    book.append(LOG_TAB, journal)
    for l in journal: print(" | ".join(str(x) for x in l))
    try:   # trace dans le dépôt GitHub (garde aussi le robot actif)
        with open(os.path.join(os.path.dirname(__file__), "derniere_execution.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(" | ".join(str(x) for x in l) for l in journal) + "\n")
    except OSError: pass
    erreurs = [l for l in journal if l[3] in ("ERREUR", "À CONFIRMER")]
    return 1 if erreurs else 0


BOOK_FACTORY = GBook
if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "robot/config_honneur.json"))
