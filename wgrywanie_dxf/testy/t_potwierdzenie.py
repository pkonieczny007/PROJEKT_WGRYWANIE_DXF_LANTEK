# -*- coding: utf-8 -*-
"""Potwierdzenie na zywym przykladzie uzytkownika (tylko SELECT)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db, ruty as R

REF = "10_S235_test-giecie_GS_"
cn = db.polacz(Config.DB)
cur = cn.cursor()
cur.execute("SELECT PrdRef, DIS_UData8_Prt, DIS_Thickness, DIS_RouteAbbreviation, "
            "DIS_MatRef, DIS_Area, CrtUser, CrtDate FROM PPRR_PPRR_00000100 WHERE PrdRef = ?", REF)
for r in cur.fetchall():
    print("produkt   :", r[0])
    print("  UData8  :", r[1])
    print("  grubosc :", r[2], "| ruta:", r[3], "| material:", r[4], "| pole:", r[5])
    print("  zalozyl :", r[6], r[7])
ops = db.operacje_po_ref(cn, [REF]).get(REF, [])
print("  marszruta w bazie:", db.marszruta_txt(ops) or "(brak)")
for o in ops:
    print("     OOrder=%s PrevOpr=%s %s / %s" % o)

szablony = R.wczytaj_z_bazy(cn)
r, kand, opis = R.przewidz(szablony, REF, 10, klasa=2)
print("\nnasze przewidywanie: ruta=%s (%s) | %s" % (r.ref if r else "-", opis,
                                                    r.opis() if r else ""))
print("pasujace ruty:", [k.ref for k in kand])
