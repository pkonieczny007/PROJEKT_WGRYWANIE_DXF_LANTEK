# -*- coding: utf-8 -*-
"""Self-test warstwy SQL (tylko SELECT)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

cn = db.self_test(Config.DB)
print("-" * 70)
refy = ["12_S235_SL40033136_p1_1st_G_1129_", "8_S235_SL40033947_p1_2st__1129_",
        "10_S235_test_test2_G", "12_S235_SL40034102_p10_1st_S_1129_1"]
p = db.produkty_po_ref(cn, refy)
o = db.operacje_po_ref(cn, refy)
for r in refy:
    d = p.get(r)
    print("%-38s %s | %s" % (r[:38],
          ("JEST mat=%s gr=%s %s" % (d["DIS_MatRef"], d["DIS_Thickness"], d["CrtDate"])) if d else "brak w bazie",
          db.marszruta_txt(o.get(r, [])) or "-"))
print("-" * 70)
for ord_ in ("12_7453_BLACHY-test", "82_1129_BLACHY"):
    z = db.zamowienie(cn, ord_)
    print(ord_, "->", "JEST" if z else "brak", "| linii:",
          len(db.linie_zamowienia(cn, ord_)), "| max LineNum:", db.max_linia(cn, ord_))
print("wzorzec %1129%:", [x["OrdRef"] for x in db.zamowienia_wg_wzorca(cn, "%1129%")][:10])
