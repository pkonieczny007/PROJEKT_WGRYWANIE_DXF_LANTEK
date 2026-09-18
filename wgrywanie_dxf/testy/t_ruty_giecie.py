# -*- coding: utf-8 -*-
"""Wlasciwa metryka: czy przewidujemy POPRAWNIE, ze element dostanie GIECIE.

Nazwa ruty jest drugorzedna - ruty L, L+S, L+SO, P maja te same operacje
(samo 2D Cut). Realnie rozstrzyga sie tylko jedno: czy w marszrucie jest Giecie.
Tylko SELECT.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db
from services import ruty as R
from services.wspolne import rozbierz_referencje

cn = db.polacz(Config.DB)
ruty = R.wczytaj_z_bazy(cn)
mapa = {r.ref: r for r in ruty}


def ma_giecie(nazwa_ruty) -> bool:
    r = mapa.get((nazwa_ruty or "").strip())
    return bool(r and any(o[2] == "Giecie" for o in r.operacje))


cur = cn.cursor()
cur.execute("""
SELECT TOP 2000 PrdRef, DIS_UData8_Prt, DIS_Thickness, DIS_RouteAbbreviation
FROM PPRR_PPRR_00000100
WHERE DIS_RouteAbbreviation <> '' AND DIS_UData8_Prt <> '' AND DIS_PClass = 2
ORDER BY LastDate DESC
""")
wiersze = cur.fetchall()

# dodatkowo: co MY byśmy wywnioskowali z samej referencji (kod technologii)
tab = {"zgodne": 0, "my_gnie_lantek_nie": [], "lantek_gnie_my_nie": []}
tab_kod = {"zgodne": 0, "my_gnie_lantek_nie": [], "lantek_gnie_my_nie": []}

for ref, ud8, gr, faktyczna in wiersze:
    lantek_gnie = ma_giecie(faktyczna)

    r, _, _ = R.przewidz(ruty, ud8, gr, klasa=2)
    my_gnie = ma_giecie(r.ref if r else "")
    if my_gnie == lantek_gnie:
        tab["zgodne"] += 1
    elif my_gnie:
        tab["my_gnie_lantek_nie"].append((ref, gr, faktyczna))
    else:
        tab["lantek_gnie_my_nie"].append((ref, gr, faktyczna))

    kod = (rozbierz_referencje(ud8)["technologia"] or "").upper()
    kod_gnie = "G" in kod or "W" in kod
    if kod_gnie == lantek_gnie:
        tab_kod["zgodne"] += 1
    elif kod_gnie:
        tab_kod["my_gnie_lantek_nie"].append((ref, gr, faktyczna, kod))
    else:
        tab_kod["lantek_gnie_my_nie"].append((ref, gr, faktyczna, kod))

n = len(wiersze)
print("produktow (blachy z nadana ruta):", n)
print("\n--- A) przewidywanie przez interpreter regul DIS_Rules")
print("   zgodne z LANTEKIEM        : %d (%.1f%%)" % (tab["zgodne"], 100.0 * tab["zgodne"] / n))
print("   my: giecie / LANTEK: brak : %d" % len(tab["my_gnie_lantek_nie"]))
print("   LANTEK: giecie / my: brak : %d" % len(tab["lantek_gnie_my_nie"]))

print("\n--- B) przewidywanie wprost z kodu technologii w referencji (G/W)")
print("   zgodne z LANTEKIEM        : %d (%.1f%%)" % (tab_kod["zgodne"], 100.0 * tab_kod["zgodne"] / n))
print("   my: giecie / LANTEK: brak : %d" % len(tab_kod["my_gnie_lantek_nie"]))
print("   LANTEK: giecie / my: brak : %d" % len(tab_kod["lantek_gnie_my_nie"]))

print("\nprzyklady: LANTEK nadal giecie, kod w referencji nie mowi o gieciu")
for x in tab_kod["lantek_gnie_my_nie"][:8]:
    print("   %-44s gr=%-5s ruta=%-8s kod=%r" % (str(x[0])[:44], x[1], x[2], x[3]))
print("\nprzyklady: kod mowi giecie, LANTEK nie nadal")
for x in tab_kod["my_gnie_lantek_nie"][:8]:
    print("   %-44s gr=%-5s ruta=%-8s kod=%r" % (str(x[0])[:44], x[1], x[2], x[3]))
