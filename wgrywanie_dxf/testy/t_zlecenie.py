# -*- coding: utf-8 -*-
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import zlecenie as Z

for nr in ("82_1129", "61_7227"):
    t0 = time.time()
    p = Z.propozycje(nr, Config.KORZENIE_TECHNOLOGIA, Config.KORZENIE_DXF,
                     Config.GLEBOKOSC_SKANU)
    print("\n=== %s  (%.1f s)" % (nr, time.time() - t0))
    print("folder :", p["folder"])
    print("ordref :", p["ordref"])
    print("wykazy :")
    for w in p["wykazy"][:5]:
        print("   %s %s" % ("ROBOCZY" if w["roboczy"] else "       ", w["nazwa"][:80]))
    print("foldery DXF:")
    for d in p["foldery_dxf"][:8]:
        print("   %5d  %s" % (d["plikow"], d["sciezka"]))
    for u in p["uwagi"]:
        print("   UWAGA:", u)
