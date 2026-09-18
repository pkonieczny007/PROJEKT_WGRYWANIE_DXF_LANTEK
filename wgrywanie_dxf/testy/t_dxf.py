# -*- coding: utf-8 -*-
"""Test skanowania i badania DXF na realnych folderach."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import dxf_check as dx  # noqa: E402

FOLDERY = [
    r"C:\Lantek\importxml\DXF",
    r"\\QNAP-ENERGO\Technologia\2026\82_1129\DXF82\1część-6FB-DXF82-Z_BAZY",
]

for f in FOLDERY:
    t0 = time.time()
    try:
        mapa = dx.zbierz(f, podfoldery=False)
    except Exception as e:
        print(f, "->", e)
        continue
    print("\n==", f, "->", len(mapa), "nazw,", round(time.time() - t0, 2), "s")
    duple = {k: v for k, v in mapa.items() if len(v) > 1}
    print("   duplikaty nazw:", len(duple))
    probka = [v[0] for v in list(mapa.values())[:4]]
    t1 = time.time()
    for p in probka:
        w = dx.zbadaj(p)
        print("   %-46s otw=%s encji=%-5s %sx%s giecie=%s warstwy=%s%s" %
              (w.nazwa[:46], w.otwarty, w.encji, w.szer, w.wys, w.linii_giecia,
               w.warstwy[:4], (" BLAD: " + w.blad) if w.blad else ""))
    print("   4 pliki pelnym odczytem:", round(time.time() - t1, 2), "s")
    t2 = time.time()
    for p in list(mapa.values())[:50]:
        dx.zbadaj(p[0], pelny=False)
    print("   50 plikow tylko naglowek:", round(time.time() - t2, 2), "s")
