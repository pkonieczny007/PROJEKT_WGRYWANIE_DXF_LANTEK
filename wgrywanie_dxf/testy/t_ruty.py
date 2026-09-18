# -*- coding: utf-8 -*-
"""Czym sa RouRef (L+G, P+G, L+G+S...)? Czy to gotowe marszruty, ktore nadaje
Lantek Expert? (tylko SELECT)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

cn = db.polacz(Config.DB)
cur = cn.cursor()


def poka(sql, *p, n=25, tytul=""):
    print("\n###", tytul)
    try:
        cur.execute(sql, *p)
    except Exception as e:
        print("   BLAD:", e)
        return
    kol = [d[0] for d in cur.description]
    w = cur.fetchall()
    for i, r in enumerate(w):
        if i >= n:
            print("   ...", len(w) - n, "wiecej")
            break
        print("   " + " ; ".join("%s=%s" % (k, "" if v is None else v) for k, v in zip(kol, r)))
    if not w:
        print("   (brak wierszy)")


poka("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='MMNN_PPOO_00000100' "
     "ORDER BY ORDINAL_POSITION", n=40, tytul="kolumny MMNN_PPOO_00000100 (naglowki rut?)")

poka("SELECT TOP 25 * FROM MMNN_PPOO_00000100", n=25, tytul="zawartosc MMNN_PPOO_00000100")

poka("SELECT RouRef, COUNT(*) ile, MIN(CrtDate) od_, MAX(CrtDate) do_ "
     "FROM MMNN_PPOO_00000200 WHERE RouRef <> '' GROUP BY RouRef ORDER BY 2 DESC", n=25,
     tytul="ile wierszy marszrut ma niepuste RouRef")

poka("SELECT TOP 12 PrdRef, OOrder, WrkRef, OprRef, RouRef, CrtUser, CrtDate "
     "FROM MMNN_PPOO_00000200 WHERE RouRef = 'L+G' ORDER BY CrtDate DESC", n=12,
     tytul="przyklad wierszy z RouRef = L+G")

poka("SELECT TOP 10 PrdRef, DIS_RouteAbbreviation, DIS_Area, CrtUser, LastUser, CrtDate "
     "FROM PPRR_PPRR_00000100 WHERE DIS_RouteAbbreviation <> '' ORDER BY LastDate DESC", n=10,
     tytul="produkty ze skrotem marszruty DIS_RouteAbbreviation")

poka("SELECT DIS_RouteAbbreviation, COUNT(*) ile FROM PPRR_PPRR_00000100 "
     "WHERE DIS_RouteAbbreviation <> '' GROUP BY DIS_RouteAbbreviation ORDER BY 2 DESC", n=25,
     tytul="rozklad DIS_RouteAbbreviation")

# jak wyglada produkt, ktoremu Expert nadal marszrute 5.03.2026
poka("SELECT PrdRef, DIS_RouteAbbreviation, DIS_MatRef, DIS_Thickness, DIS_Area, "
     "CrtUser, CrtDate, LastUser, LastDate FROM PPRR_PPRR_00000100 "
     "WHERE PrdRef = ?", "1,5_DC01_SL40551305_p2_1st_G_2026_", n=5,
     tytul="produkt z 5.03.2026: wgrany XML-em, marszruta dopisana w Expercie")
