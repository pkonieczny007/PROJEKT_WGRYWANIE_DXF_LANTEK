# -*- coding: utf-8 -*-
"""Czy druga operacja przy produkcie Z GEOMETRIA pochodzi z tego samego importu,
czy zostala dopisana pozniej? (tylko SELECT)

Jesli druga operacja zawsze powstaje POZNIEJ (inny czas / inny uzytkownik), to
znaczy, ze import XML jej nie utrzymuje - ktos dopisywal ja recznie w Expercie.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

cn = db.polacz(Config.DB)
cur = cn.cursor()

SQL = """
SELECT TOP 400
       p.PrdRef, p.CrtDate AS prod_data, p.DIS_Area AS pole,
       o1.CrtDate AS op1_data, o1.CrtUser AS op1_user, o1.OprRef AS op1,
       o2.CrtDate AS op2_data, o2.CrtUser AS op2_user, o2.OprRef AS op2
FROM PPRR_PPRR_00000100 p
JOIN MMNN_PPOO_00000200 o1 ON o1.PrdRef = p.PrdRef AND o1.OOrder = 1
JOIN MMNN_PPOO_00000200 o2 ON o2.PrdRef = p.PrdRef AND o2.OOrder = 2
WHERE p.CrtUser = 'SYSADM' AND p.DIS_Area > 0
ORDER BY p.CrtDate DESC
"""
cur.execute(SQL)
kol = [d[0] for d in cur.description]
w = [dict(zip(kol, r)) for r in cur.fetchall()]
print("produkty z geometria + 2 operacje, zalozone importem:", len(w))

ten_sam, pozniej, inny_user = 0, 0, 0
for r in w:
    dt = (r["op2_data"] - r["op1_data"]).total_seconds()
    if r["op2_user"] != "SYSADM":
        inny_user += 1
    elif abs(dt) <= 60:
        ten_sam += 1
    else:
        pozniej += 1
print("  druga operacja z tego samego importu (<=60 s, SYSADM):", ten_sam)
print("  druga operacja SYSADM, ale pozniej             :", pozniej)
print("  druga operacja dopisana przez czlowieka         :", inny_user)

print("\nprobka (najnowsze):")
print("  %-40s %-19s %-19s %-12s %s" % ("PrdRef", "op1", "op2", "op2_user", "roznica_s"))
for r in w[:12]:
    dt = (r["op2_data"] - r["op1_data"]).total_seconds()
    print("  %-40s %-19s %-19s %-12s %.0f  (%s -> %s)" %
          (str(r["PrdRef"])[:40], str(r["op1_data"])[:19], str(r["op2_data"])[:19],
           r["op2_user"], dt, r["op1"], r["op2"]))

print("\n### to samo dla produktow BEZ geometrii (kontrola)")
cur.execute(SQL.replace("p.DIS_Area > 0", "(p.DIS_Area IS NULL OR p.DIS_Area = 0)"))
w2 = [dict(zip(kol, r)) for r in cur.fetchall()]
ten_sam2 = sum(1 for r in w2
               if r["op2_user"] == "SYSADM" and abs((r["op2_data"] - r["op1_data"]).total_seconds()) <= 60)
print("  produktow:", len(w2), "| druga operacja z tego samego importu:", ten_sam2)
for r in w2[:6]:
    dt = (r["op2_data"] - r["op1_data"]).total_seconds()
    print("  %-40s %-19s %-19s %-12s %.0f  (%s -> %s)" %
          (str(r["PrdRef"])[:40], str(r["op1_data"])[:19], str(r["op2_data"])[:19],
           r["op2_user"], dt, r["op1"], r["op2"]))
