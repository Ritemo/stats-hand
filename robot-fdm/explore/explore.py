import sys, os, json, datetime
sys.path.insert(0, "robot-fdm/robot"); os.environ["NTFY_OFF"] = "1"
import robot, coupes
class FakeBook:
    def __init__(s): s.t = {}
    def read_all(s, tab): return s.t.get(tab)
    def ensure(s, tab, h): s.t.setdefault(tab, [h])
    def replace(s, tab, rows, raw=False): s.t[tab] = [[str(x) for x in r] for r in rows]
for cfgp in ["config_honneur.json", "config_n3f.json"]:
    cfg = json.load(open("robot-fdm/robot/" + cfgp)); b = FakeBook(); j = []
    ici = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    for passe in (1, 2):
        coupes.maj_coupes(b, cfg, "reel", ici, ici.strftime("%d/%m/%Y %H:%M"), j, robot.fetch, robot.fdm_url, robot.parse_fdm, robot.parse_deroule, robot.salle_rencontre, robot.notifier)
    print("####", cfgp, j)
    for r in b.t["_Coupes"]: print(" ROW", r)
