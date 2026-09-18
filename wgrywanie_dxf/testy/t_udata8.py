# -*- coding: utf-8 -*-
"""Reguly rut (MMNN_PPOO_00000100.DIS_Rules) czytaja pole UData8.
Co siedzi w UData8 produktow, ktore dostaly marszrute z gieciem? (tylko SELECT)"""
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


poka("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='PPRR_PPRR_00000100' "
     "AND (COLUMN_NAME LIKE '%UData%' OR COLUMN_NAME LIKE '%Route%') ORDER BY ORDINAL_POSITION",
     n=30, tytul="pola UData i Route w tabeli produktow")

poka("SELECT DIS_RouteAbbreviation, COUNT(*) ile FROM PPRR_PPRR_00000100 "
     "GROUP BY DIS_RouteAbbreviation ORDER BY 2 DESC", n=25,
     tytul="rozklad skrotu marszruty na wszystkich produktach")

poka("SELECT TOP 12 PrdRef, DIS_RouteAbbreviation AS ruta, DIS_UData8_Prt AS udata8, "
     "DIS_Thickness AS gr, CrtUser, CrtDate FROM PPRR_PPRR_00000100 "
     "WHERE DIS_RouteAbbreviation LIKE '%G%' ORDER BY CrtDate DESC", n=12,
     tytul="produkty z ruta zawierajaca G - co maja w UData8")

poka("SELECT TOP 12 PrdRef, DIS_RouteAbbreviation AS ruta, DIS_UData8_Prt AS udata8, "
     "DIS_Thickness AS gr, CrtUser, CrtDate FROM PPRR_PPRR_00000100 "
     "WHERE PrdRef LIKE '%\\_G\\_%' ESCAPE '\\' ORDER BY CrtDate DESC", n=12,
     tytul="produkty, ktorych REFERENCJA ma _G_ - jaka dostaly rute")

poka("SELECT TOP 8 PrdRef, DIS_RouteAbbreviation AS ruta, DIS_UData8_Prt AS udata8, "
     "DIS_UData1_Prt AS udata1, DIS_Thickness AS gr, CrtUser "
     "FROM PPRR_PPRR_00000100 WHERE PrdRef IN "
     "('10_S235_test_test2_G','5_S235_SL10585779_p1A_1st_G_1847__Z',"
     " '1,5_DC01_SL40551305_p2_1st_G_2026_','12_S235_SL40034102_p10_1st_S_1129_1')", n=8,
     tytul="nasze przyklady: testowy (XML) vs nadane w Expercie")

poka("SELECT COUNT(*) AS produktow, SUM(CASE WHEN DIS_UData8_Prt <> '' THEN 1 ELSE 0 END) AS z_udata8 "
     "FROM PPRR_PPRR_00000100", n=3, tytul="ilu produktom w ogole wypelniono UData8")
