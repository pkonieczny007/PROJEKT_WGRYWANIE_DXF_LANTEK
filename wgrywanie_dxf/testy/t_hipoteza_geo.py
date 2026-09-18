# -*- coding: utf-8 -*-
"""HIPOTEZA: import geometrii (IMPORTGEO) kasuje operacje wgrane wczesniej w tym
samym pliku XML - dlatego z marszruty zostaje samo wypalanie.

Test: produkty zalozone przez import XML (CrtUser=SYSADM). Czy te, ktore MAJA
2 operacje, maja geometrie (DIS_Area>0)? Jesli nie - hipoteza potwierdzona.
Tylko SELECT.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

cn = db.polacz(Config.DB)
cur = cn.cursor()

SQL = """
SELECT p.PrdRef,
       o.ile            AS operacji,
       p.DIS_Area       AS pole,
       p.DIS_CutPerim   AS obwod,
       p.CrtUser, p.CrtDate
FROM PPRR_PPRR_00000100 p
JOIN (SELECT PrdRef, COUNT(*) ile FROM MMNN_PPOO_00000200
      WHERE CrtUser = 'SYSADM' GROUP BY PrdRef) o ON o.PrdRef = p.PrdRef
WHERE p.CrtUser = 'SYSADM'
"""

cur.execute(SQL)
kol = [d[0] for d in cur.description]
w = [dict(zip(kol, r)) for r in cur.fetchall()]
print("produktow zalozonych importem XML (SYSADM) z marszruta:", len(w))

grupy = {}
for r in w:
    ma_geo = bool(r["pole"] and float(r["pole"]) > 0)
    wiele = int(r["operacji"]) > 1
    grupy.setdefault((wiele, ma_geo), []).append(r)

print("\n%-22s %-12s %7s" % ("operacji w marszrucie", "ma geometrie", "ile"))
print("-" * 46)
for (wiele, geo), lst in sorted(grupy.items()):
    print("%-22s %-12s %7d" % ("2 i wiecej" if wiele else "tylko 1",
                               "TAK" if geo else "nie", len(lst)))

for (wiele, geo), lst in sorted(grupy.items()):
    print("\n--- %s / geometria %s (%d) - probka:" %
          ("2+ operacji" if wiele else "1 operacja", "TAK" if geo else "nie", len(lst)))
    for r in lst[:5]:
        print("    %-44s ops=%s pole=%s obwod=%s %s" %
              (str(r["PrdRef"])[:44], r["operacji"], r["pole"], r["obwod"], r["CrtDate"]))

print("\n### kontrola odwrotna: produkty z 2+ operacjami zalozone RECZNIE (Expert)")
cur.execute("""
SELECT TOP 5 p.PrdRef, o.ile, p.DIS_Area, p.CrtUser, p.CrtDate
FROM PPRR_PPRR_00000100 p
JOIN (SELECT PrdRef, COUNT(*) ile FROM MMNN_PPOO_00000200 GROUP BY PrdRef) o
     ON o.PrdRef = p.PrdRef
WHERE o.ile > 1 AND p.CrtUser <> 'SYSADM' AND p.DIS_Area > 0
ORDER BY p.CrtDate DESC
""")
for r in cur.fetchall():
    print("    %-44s ops=%s pole=%s %s %s" % (str(r[0])[:44], r[1], r[2], r[3], r[4]))
