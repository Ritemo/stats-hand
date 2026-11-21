"""Matchs de coupe du Pays Riolais (Coupe de France régionale, etc.), rangés à part dans l'onglet _Coupes.

Ils ne comptent dans aucune statistique du championnat : l'appli les affiche seulement dans un écran « Coupe ».
Le robot trouve tout seul les coupes où le club est engagé (même numéro de club que l'équipe du championnat,
réglage « coupe_club » de la configuration) parmi les coupes du genre choisi (« coupe_genre »).

Pour ménager le site de la fédération :
  - recherche complète (toutes les coupes, tous les tours) au plus toutes les 12 heures ;
  - entre deux, seuls les matchs de Rioz commencés et pas encore terminés sont relus (une page chacun).
"""
import re, json, html, datetime, unicodedata
from fdm import parse_events, evenements

B = "https://www.ffhandball.fr/competitions/saison-2026-2027-22/coupe-de-france/"
TAB = "_Coupes"
HEAD = ["Competition", "Tour", "Date", "Domicile", "Extérieur", "Score dom", "Score ext", "MT dom", "MT ext", "Nous",
        "Salle", "Adresse", "Lat", "Lng", "FDM", "Joueurs", "Deroule", "Poule", "Rid", "Equipement", "Notif", "Mise a jour", "Evts"]
NIVEAU = {"NATIONALE": "nationale", "FEDERALE": "fédérale", "REGIONALE": "régionale", "DEPARTEMENTALE": "départementale"}


def _comps(page):
    for m in re.finditer(r'<smartfire-component([^>]*?)attributes="([^"]*)"', page or ""):
        n = re.search(r"name='([^']*)'", m.group(1))
        try: yield (n.group(1) if n else ""), json.loads(html.unescape(m.group(2)))
        except ValueError: pass


def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def nom_coupe(lib):
    """« COUPE DE FRANCE CAISSE D'EPARGNE REGIONALE MASCULINE 2026-2027 » -> « Coupe de France régionale »."""
    niv = next((v for k, v in NIVEAU.items() if k in lib.upper()), "")
    if "COUPE DE FRANCE" in lib.upper(): return ("Coupe de France " + niv).strip()
    return lib.title()


def nom_tour(phase, poule):
    """Phase « CDF REG MAS (3° TOUR) » et poule « TOURNOI 2 » -> « 3e tour (tournoi 2) »."""
    def norm(s):
        s = re.sub(r"(\d+)\s*(?:°|ER\b|EME\b|E\b)", lambda m: m.group(1) + ("er" if m.group(1) == "1" else "e"), s.upper())
        return s.lower().strip()
    m = re.search(r"\(([^)]*TOUR[^)]*)\)", phase or "")
    p = norm(poule or "")
    if m:
        t = norm(m.group(1))
        return t if p in ("", t) else f"{t} ({p})"
    return p or norm(phase or "")


def _ligne(old, x, comp, tour, poule_url, ids):
    d = {k: "" for k in HEAD}; d.update(old or {})
    nous = "D" if _nous(x, 1, ids) else "E"
    d.update({"Competition": comp, "Tour": tour, "Domicile": x["equipe1Libelle"], "Extérieur": x["equipe2Libelle"],
              "Nous": nous, "Poule": poule_url, "Rid": str(x.get("ext_rencontreId") or "")})
    if x.get("date"): d["Date"] = x["date"][:16]
    for k, v in (("Score dom", "equipe1Score"), ("Score ext", "equipe2Score"), ("MT dom", "equipe1ScoreMT"), ("MT ext", "equipe2ScoreMT")):
        if x.get(v) not in (None, ""): d[k] = str(x[v])
    if x.get("fdmCode"): d["FDM"] = x["fdmCode"]
    if x.get("equipementId"): d["Equipement"] = str(x["equipementId"])
    return d


NOM = "RIOLAIS"      # repli : nom de l'équipe dans les coupes (« PAYS RIOLAIS HANDBALL »)


def _nous(x, k, ids):
    return str(x.get(f"equipe{k}Id")) in ids or NOM in (x.get(f"equipe{k}Libelle") or "").upper()


def _rencontres(fetch, poule_url, n_journees):
    out = []
    for j in range(1, max(1, n_journees) + 1):
        for n, c in _comps(fetch(f"{poule_url}journee-{j}/")):
            if n == "competitions---rencontre-list": out += c.get("rencontres") or []
    return out


def joue(d):
    return str(d.get("Score dom") or "").strip() != "" and str(d.get("Score ext") or "").strip() != ""


def maj_coupes(book, cfg, mode, ici, now, journal, fetch, fdm_url, parse_fdm, parse_deroule, salle_rencontre, notifier):
    club, genre = str(cfg.get("coupe_club") or ""), (cfg.get("coupe_genre") or "").upper()
    if not club or not genre: return
    old = book.read_all(TAB) or []
    head = old[0] if old else HEAD
    rows, scan = {}, ""
    for r in old[1:]:
        d = dict(zip(head, r + [""] * (len(head) - len(r))))
        if d.get("Competition") == "_scan": scan = d.get("Date", ""); continue
        if d.get("Rid"): rows[d["Rid"]] = d
    try: dernier = datetime.datetime.strptime(scan, "%Y-%m-%dT%H:%M")
    except ValueError: dernier = None
    complet = mode == "rattrapage" or not dernier or ici - dernier >= datetime.timedelta(hours=12)
    debut = lambda d: datetime.datetime.strptime(d["Date"], "%Y-%m-%dT%H:%M") if re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d", d.get("Date") or "") else None
    n_pages = 0

    if complet:
        menu = next((c for n, c in _comps(fetch(B)) if n == "competitions---competition-main-menu"), None)
        if not menu: raise RuntimeError("page des coupes de France illisible (le site a peut-être changé)")
        n_pages += 1
        for comp in menu.get("competitions") or []:
            if (comp.get("genre") or "").upper() != genre: continue
            url = f"{B}{_slug(comp['libelle'])}-{comp['ext_competitionId']}/"
            ids, poules, phases = set(), [], {}
            for n, c in _comps(fetch(url)):
                if n == "competitions---calendar-button":
                    ids = {str(e.get("id")) for e in c.get("equipes") or [] if str(e.get("ext_structureId")) == club}
                if n == "competitions---poule-selector":
                    poules = c.get("poules") or []; phases = {p.get("id"): p.get("libelle", "") for p in c.get("phases") or []}
            n_pages += 1
            if not ids: continue
            nom = nom_coupe(comp["libelle"])
            for p in poules:
                try: js = json.loads(p.get("journees") or "[]")
                except ValueError: js = []
                dates = [datetime.datetime.strptime(x["date_debut"], "%Y-%m-%d") for x in js if x.get("date_debut")]
                if dates and not (ici - datetime.timedelta(days=150) <= max(dates) and min(dates) <= ici + datetime.timedelta(days=30)): continue
                pu = f"{url}poule-{p['ext_pouleId']}/"
                connus = [d for d in rows.values() if d.get("Poule") == pu]
                if connus and all(joue(d) and d.get("Joueurs") and d.get("Evts") for d in connus): continue    # tour déjà complet chez nous
                for x in _rencontres(fetch, pu, len(js)):
                    if _nous(x, 1, ids) or _nous(x, 2, ids):
                        x = {**x, "equipe1Id": str(x["equipe1Id"]), "equipe2Id": str(x["equipe2Id"])}
                        rid = str(x.get("ext_rencontreId") or "")
                        rows[rid] = _ligne(rows.get(rid), x, nom, nom_tour(phases.get(p.get("phaseId")), p.get("libelle")), pu, ids)
                n_pages += max(1, len(js))
        scan = ici.strftime("%Y-%m-%dT%H:%M")
    else:
        for d in list(rows.values()):          # entre deux recherches : seulement les matchs en cours ou à peine finis
            t = debut(d)
            if joue(d) or not t or not (t <= ici <= t + datetime.timedelta(days=3)): continue
            for x in _rencontres(fetch, d["Poule"], 1):
                if str(x.get("ext_rencontreId")) == d["Rid"]:
                    ids = {str(x["equipe1Id"] if d.get("Nous") == "D" else x["equipe2Id"])}
                    x = {**x, "equipe1Id": str(x["equipe1Id"]), "equipe2Id": str(x["equipe2Id"])}
                    rows[d["Rid"]] = _ligne(d, x, d["Competition"], d["Tour"], d["Poule"], ids)
            n_pages += 1

    n_fdm = 0
    for rid, d in rows.items():
        t = debut(d)
        # salle (une fois par match)
        if not d.get("Salle") and d.get("Rid") and (not t or t >= ici - datetime.timedelta(days=2)):
            s = salle_rencontre(d["Poule"], rid)
            if s: d.update({"Salle": s["salle"], "Adresse": s["adresse"], "Lat": s["lat"], "Lng": s["lng"]})
        # feuille de match : joueurs, déroulé ; score lu sur la feuille si le site ne l'affiche pas encore
        if not d.get("FDM") or (joue(d) and d.get("Joueurs") and d.get("Evts")): continue
        if joue(d) and not (str(d["Score dom"]).isdigit() and str(d["Score ext"]).isdigit()): continue     # forfait : pas de feuille de match
        if not joue(d) and not (t and t + datetime.timedelta(minutes=80) <= ici <= t + datetime.timedelta(days=30)): continue
        data = fetch(fdm_url(d["FDM"]), binary=True); n_fdm += 1
        if not data: continue
        try:
            f = parse_fdm(data)
            if not joue(d):
                if not (f["score"] and sum(f["score"]) > 0): continue
                d["Score dom"], d["Score ext"] = str(f["score"][0]), str(f["score"][1])
            d["Joueurs"] = "|".join(f"{'DE'[i]}:{p['nom'].replace('|', ' ').replace(':', ' ').replace('=', ' ')}="
                                    f"{p['buts']},{p['tirs']},{p['excl']},{'' if p['arrets'] is None else p['arrets']},{p['7m']}"
                                    for i, e in enumerate(f["equipes"]) for p in e["joueurs"])
            d["Deroule"] = " ".join(f"{s}:{h}-{a}" for s, h, a in parse_deroule(data)) or "ND"
            d["Evts"] = evenements(f, parse_events(data)) or "ND"      # déroulé détaillé : sert aux notes du match
        except Exception as e:
            journal.append([now, "", f"Coupe {d['Domicile']} - {d['Extérieur']}", "ERREUR", f"feuille de match illisible : {e}"])

    # notification du résultat de Rioz (une fois ; pas pour les vieux matchs découverts après coup)
    for d in rows.values():
        if not joue(d) or d.get("Notif"): continue
        t = debut(d)
        if t and ici - t <= datetime.timedelta(days=3):
            court = lambda s: re.sub(r"\s+(HB|HBC|HANDBALL|HAND BALL|CLUB)$", "", s.strip(), flags=re.I).title()
            notifier(cfg, f"Coupe : {court(d['Domicile'])} {d['Score dom']}-{d['Score ext']} {court(d['Extérieur'])}",
                     f"{d['Competition']}, {d['Tour']} (hors championnat)", (cfg.get("app_url") or "") + "#/coupe")
        d["Notif"] = now

    d0 = sorted(rows.values(), key=lambda d: d.get("Date") or "")
    for d in d0: d["Mise a jour"] = d.get("Mise a jour") or now
    out = [[d.get(k, "") for k in HEAD] for d in d0] + [["_scan", "", scan] + [""] * (len(HEAD) - 3)]
    book.ensure(TAB, HEAD)
    book.replace(TAB, [HEAD] + out, raw=True)
    try: print(f"onglet {TAB} : {len(d0)} match(s) de coupe, gid {book._ws[TAB].id}, {n_pages} page(s) lues, {n_fdm} feuille(s)")
    except Exception: pass
