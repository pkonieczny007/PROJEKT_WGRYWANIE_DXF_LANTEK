# -*- coding: utf-8 -*-
"""Weryfikacja pierwszego prawdziwego wgrania z aplikacji (tylko SELECT)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

REFY = ["5_S235_TS99911112_p1_1st_G_0199TEST_P",
        "5_S235_TS99911112_p2_1st_G_0199TEST_L",
        "5_S235_TS99911112_p3_1st_G_0199TEST_"]
ORD = "199_9999_BLACHY"

cn = db.polacz(Config.DB)
cur = cn.cursor()
cur.execute("SELECT PrdRef, DIS_UData8_Prt, DIS_MatRef, DIS_Thickness, "
            "DIS_RouteAbbreviation, DIS_Area, CrtUser, CrtDate "
            "FROM PPRR_PPRR_00000100 WHERE PrdRef IN (?,?,?)", *REFY)
print("=== PRODUKTY W KARTOTECE")
for r in cur.fetchall():
    print("  %-44s mat=%-8s gr=%-5s ruta=%-6s geometria=%-10s %s %s"
          % (r[0], r[2], r[3], r[4] or "(brak)", r[5], r[6], r[7]))
    print("      UData8 = %s  %s" % (r[1], "== PrdRef" if r[1] == r[0] else "!! ROZNE"))

print("\n=== MARSZRUTY")
ops = db.operacje_po_ref(cn, REFY)
for ref in REFY:
    lista = ops.get(ref, [])
    ma_giecie = any(o[3] == "Giecie" for o in lista)
    print("  %-44s %-24s %s" % (ref, db.marszruta_txt(lista) or "(brak)",
                                "GIECIE JEST" if ma_giecie else "BRAK GIECIA"))

print("\n=== ZAMOWIENIE SPRZEDAZY", ORD)
z = db.zamowienie(cn, ORD)
print("  naglowek:", "JEST" if z else "brak", z if z else "")
for l in db.linie_zamowienia(cn, ORD):
    print("  linia %-4s %-44s ilosc %s" % (l["LineNum"], l["PrdRef"], l["Quantity"]))
