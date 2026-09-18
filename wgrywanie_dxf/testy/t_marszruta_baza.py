# -*- coding: utf-8 -*-
"""Gdzie naprawde ladauje operacja 'Giecie' po imporcie? (tylko SELECT)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

cn = db.polacz(Config.DB)
cur = cn.cursor()


def poka(sql, *p, n=40, tytul=""):
    print("\n###", tytul or sql[:120].replace("\n", " "))
    try:
        cur.execute(sql, *p)
    except Exception as e:
        print("   BLAD:", e)
        return []
    kol = [d[0] for d in cur.description]
    w = cur.fetchall()
    print("   " + " | ".join(kol))
    for i, r in enumerate(w):
        if i >= n:
            print("   ...", len(w) - n, "wiecej")
            break
        print("   " + " | ".join("" if v is None else str(v) for v in r))
    return w


# 1. gdzie w ogole wystepuje kolumna WrkRef
poka("SELECT TABLE_NAME, COUNT(*) AS kolumn FROM INFORMATION_SCHEMA.COLUMNS "
     "WHERE COLUMN_NAME IN ('WrkRef','OprRef') GROUP BY TABLE_NAME ORDER BY TABLE_NAME",
     tytul="tabele z WrkRef/OprRef")

# 2. wszystkie operacje testowych produktow wgranych dzis
poka("SELECT PrdRef, OOrder, PrevOpr, WrkRef, OprRef, CrtDate, CrtUser "
     "FROM MMNN_PPOO_00000200 WHERE PrdRef LIKE '10_S%test%' ORDER BY PrdRef, OOrder",
     tytul="marszruty produktow testowych (10_S..test..)")

# 3. co w ogole wpadlo do tabeli operacji dzisiaj
poka("SELECT PrdRef, OOrder, PrevOpr, WrkRef, OprRef, CrtDate FROM MMNN_PPOO_00000200 "
     "WHERE CrtDate >= '2026-09-18' ORDER BY CrtDate DESC", n=30,
     tytul="operacje utworzone dzisiaj")

# 4. czy 'Gietarka' w ogole wystepuje w marszrutach i jak czesto / od kiedy
poka("SELECT WrkRef, OprRef, COUNT(*) AS ile, MIN(CrtDate) AS od, MAX(CrtDate) AS do_ "
     "FROM MMNN_PPOO_00000200 GROUP BY WrkRef, OprRef ORDER BY MAX(CrtDate) DESC", n=40,
     tytul="centrum+operacja: ile i kiedy ostatnio (co jest ZYWE)")

# 5. jak wyglada marszruta typowej blachy gietej wgranej przez Lantek Expert
poka("SELECT TOP 40 o.PrdRef, o.OOrder, o.PrevOpr, o.WrkRef, o.OprRef, o.CrtDate "
     "FROM MMNN_PPOO_00000200 o WHERE o.PrdRef IN ("
     "  SELECT TOP 8 PrdRef FROM MMNN_PPOO_00000200 WHERE OprRef = 'Giecie' "
     "  ORDER BY CrtDate DESC) ORDER BY o.PrdRef, o.OOrder",
     tytul="marszruty ostatnich pozycji z operacja Giecie")

# 6. struktura tabeli operacji
poka("SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS "
     "WHERE TABLE_NAME='MMNN_PPOO_00000200' ORDER BY ORDINAL_POSITION", n=40,
     tytul="kolumny MMNN_PPOO_00000200")
