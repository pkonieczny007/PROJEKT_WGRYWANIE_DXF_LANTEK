# -*- coding: utf-8 -*-
"""Dlaczego druga operacja (Giecie) nie wchodzi przez import XML? (tylko SELECT)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

cn = db.polacz(Config.DB)
cur = cn.cursor()


def poka(sql, *p, n=30, tytul=""):
    print("\n###", tytul or sql[:110].replace("\n", " "))
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


poka("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
     "WHERE TABLE_NAME='MMNN_PPOO_00000200' ORDER BY ORDINAL_POSITION", n=60,
     tytul="wszystkie kolumny tabeli operacji produktu")

poka("SELECT * FROM MMNN_PPOO_00000200 WHERE PrdRef = ?",
     "10_S235_test_test2_G", tytul="ZLY przypadek: wgrany XML-em dzis (tylko 2D Cut)")

poka("SELECT * FROM MMNN_PPOO_00000200 WHERE PrdRef = ? ORDER BY OOrder",
     "5_S235_SL10585779_p1A_1st_G_1847__Z",
     tytul="DOBRY przypadek: 2D Cut + Giecie (16.09.2026)")

poka("SELECT PrdRef, OOrder, WrkRef, OprRef, RouRef, CrtUser, CrtDate "
     "FROM MMNN_PPOO_00000200 WHERE OprRef='Giecie' AND CrtUser='SYSADM' "
     "ORDER BY CrtDate DESC", n=15,
     tytul="czy import XML (SYSADM) KIEDYKOLWIEK wstawil Giecie")

poka("SELECT CrtUser, COUNT(*) ile, MIN(CrtDate) od_, MAX(CrtDate) do_ "
     "FROM MMNN_PPOO_00000200 WHERE OprRef='Giecie' GROUP BY CrtUser ORDER BY 2 DESC", n=20,
     tytul="kto zaklada operacje Giecie")

poka("SELECT TOP 20 PrdRef, OOrder, WrkRef, OprRef, RouRef, CrtUser, CrtDate "
     "FROM MMNN_PPOO_00000200 WHERE CrtUser='SYSADM' ORDER BY CrtDate DESC", n=20,
     tytul="ostatnie operacje zalozone przez SYSADM (czyli przez import XML)")

poka("SELECT DISTINCT RouRef FROM MMNN_PPOO_00000200", n=30, tytul="jakie RouRef wystepuja")

poka("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'MMNN_PPOO%' "
     "OR TABLE_NAME LIKE '%ROU%' ORDER BY 1", n=30, tytul="tabele marszrut/rut")
