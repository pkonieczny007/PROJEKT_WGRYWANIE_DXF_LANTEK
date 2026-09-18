# -*- coding: utf-8 -*-
"""Gdzie podziala sie operacja Giecie z importu 110142? (tylko SELECT)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

cn = db.polacz(Config.DB)
cur = cn.cursor()
REF = "10_S235_test_test2_G"


def poka(sql, *p, n=20, tytul=""):
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


# 1. wszystkie tabele majace kolumne PrdRef - gdzie siedzi nasz testowy produkt
cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME='PrdRef' "
            "AND TABLE_NAME NOT LIKE 'Stary%' ORDER BY 1")
tabele = [r[0] for r in cur.fetchall()]
print("### tabele z kolumna PrdRef:", len(tabele))
for t in tabele:
    try:
        cur.execute("SELECT COUNT(*) FROM [%s] WHERE PrdRef = ?" % t, REF)
        n = cur.fetchone()[0]
        if n:
            print("   %-28s -> %d wierszy" % (t, n))
    except Exception:
        pass

# 2. tabela operacji zlecen produkcyjnych
poka("SELECT TOP 10 * FROM MMNN_PPOO_00000300 WHERE PrdRef = ?", REF, n=10,
     tytul="MMNN_PPOO_00000300 dla produktu testowego")

# 3. co siedzi w produkcie (czy ma przypisana rute)
poka("SELECT PrdRef, PrdName, DIS_MatRef, DIS_Thickness, DIS_PClass, RouRef, CrtDate, LastDate "
     "FROM PPRR_PPRR_00000100 WHERE PrdRef LIKE '10_S%test%' ORDER BY LastDate DESC", n=10,
     tytul="produkty testowe - czy maja RouRef")

# 4. przyklad produktu wgranego XML-em, ktory MA giecie (grudzien 2025)
poka("SELECT PrdRef, OOrder, PrevOpr, WrkRef, OprRef, RouRef, OTime, CrtUser, CrtDate, LastDate "
     "FROM MMNN_PPOO_00000200 WHERE PrdRef = ? ORDER BY OOrder",
     "2_oc_SL10571186_p42_G_1st_SEMI", n=10,
     tytul="XML-em z Gieciem (18.12.2025) - jak wyglada")

# 5. czy w tabeli produktow jest kolumna RouRef
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME='PPRR_PPRR_00000100' AND COLUMN_NAME LIKE '%Rou%'")
print("\n### kolumny Rou* w tabeli produktow:", [r[0] for r in cur.fetchall()])

# 6. czy istnieje slownik rut
cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'MMNN_RR%' "
            "OR TABLE_NAME LIKE 'MMNN_PPOO%'")
print("### tabele rut/operacji:", [r[0] for r in cur.fetchall()])

# 7. ile wierszy operacji ma kazdy z produktow wgranych przez XML w 2025-12-18
poka("SELECT PrdRef, COUNT(*) ile, MIN(CrtDate) od_ FROM MMNN_PPOO_00000200 "
     "WHERE CrtDate >= '2025-12-18' AND CrtDate < '2025-12-19' GROUP BY PrdRef ORDER BY 3", n=20,
     tytul="import z 18.12.2025: ile operacji na produkt")
