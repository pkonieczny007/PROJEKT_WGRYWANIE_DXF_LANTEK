# -*- coding: utf-8 -*-
"""Czy nasz interpreter regul przewiduje te sama rute, ktora LANTEK faktycznie
nadal produktom? Walidacja na realnych danych (tylko SELECT)."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db
from services import ruty as R

cn = db.polacz(Config.DB)
ruty = R.wczytaj_z_bazy(cn)
print("szablonow rut:", len(ruty))
for r in sorted(ruty, key=lambda x: x.ref):
    print("   %-24s dflt=%-5s klasa=%-4s ops=%-28s warunkow=%d" %
          (r.ref, r.domyslna, r.klasa, r.opis() or "(brak)", len(R.parsuj_warunki(r.warunki_xml))))

# walidacja na produktach, ktorym LANTEK/Expert nadal rute (blachy: DIS_PClass=2)
cur = cn.cursor()
cur.execute("""
SELECT TOP 500 PrdRef, DIS_UData8_Prt, DIS_Thickness, DIS_RouteAbbreviation
FROM PPRR_PPRR_00000100
WHERE DIS_RouteAbbreviation <> '' AND DIS_UData8_Prt <> '' AND DIS_PClass = 2
ORDER BY LastDate DESC
""")
wiersze = cur.fetchall()
print("\nprodukty do walidacji:", len(wiersze))

trafione, pudla, licznik = 0, [], Counter()
for ref, ud8, gr, faktyczna in wiersze:
    r, kand, opis = R.przewidz(ruty, ud8, gr, klasa=2)
    przew = r.ref if r else "(brak)"
    faktyczna = (faktyczna or "").strip()
    licznik[(przew, faktyczna)] += 1
    if przew == faktyczna:
        trafione += 1
    else:
        pudla.append((ref, ud8, gr, faktyczna, przew, opis))

print("trafione: %d / %d (%.0f%%)" % (trafione, len(wiersze), 100.0 * trafione / max(1, len(wiersze))))
print("\nnajczestsze pary (przewidziana -> faktyczna):")
for (p, f), n in licznik.most_common(12):
    print("   %-10s -> %-14s %5d %s" % (p, f, n, "OK" if p == f else "ROZJAZD"))

print("\nprzyklady rozjazdow:")
for ref, ud8, gr, fakt, przew, opis in pudla[:10]:
    print("   %-42s gr=%-5s faktyczna=%-10s przewidziana=%-10s (%s)" %
          (str(ref)[:42], gr, fakt, przew, opis))
