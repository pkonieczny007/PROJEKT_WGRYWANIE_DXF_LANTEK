# -*- coding: utf-8 -*-
"""Czy gatunki z referencji trafiaja w ISTNIEJACE materialy LANTEKA. Tylko SELECT."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db
from services.kontrola import MATERIALY, material_lantek

cn = db.polacz(Config.DB)
cur = cn.cursor()

# 1. skad brac liste materialow
print("### tabele materialow")
cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_NAME LIKE '%MMTT%' ORDER BY 1")
for r in cur.fetchall():
    print("   ", r[0])

mat = db.materialy(cn)
print("\n### materialy z db.materialy():", len(mat))
print("   ", sorted(mat))

# 2. jakie MatRef faktycznie siedza na produktach (to jest prawda produkcyjna)
cur.execute("SELECT DIS_MatRef, COUNT(*) FROM PPRR_PPRR_00000100 "
            "WHERE DIS_MatRef <> '' GROUP BY DIS_MatRef ORDER BY 2 DESC")
uzywane = [(r[0].strip(), r[1]) for r in cur.fetchall()]
print("\n### MatRef uzywane na produktach:", len(uzywane))
for m, n in uzywane[:30]:
    print("   %-22s %7d" % (m, n))

nazwy_uzywane = {m for m, _ in uzywane}

# 3. weryfikacja mapowania
print("\n### mapowanie gatunek -> MatRef")
print("   %-18s %-22s %-12s %s" % ("gatunek z referencji", "MatRef", "w slowniku", "na produktach"))
zle = []
for gat, ref in sorted(MATERIALY.items()):
    w_slowniku = "TAK" if (not mat or ref in mat) else "NIE"
    na_prod = next((n for m, n in uzywane if m == ref), 0)
    print("   %-18s %-22s %-12s %d" % (gat, ref, w_slowniku, na_prod))
    if na_prod == 0:
        zle.append((gat, ref))
if zle:
    print("\n   UWAGA - te MatRef nie wystepuja na zadnym produkcie:", zle)

# 4. gatunki spotykane w referencjach blach w bazie - czy wszystkie mamy w mapowaniu
cur.execute("SELECT TOP 4000 PrdRef, DIS_MatRef FROM PPRR_PPRR_00000100 "
            "WHERE DIS_PClass = 2 AND PrdRef LIKE '%\\_%' ESCAPE '\\' "
            "ORDER BY LastDate DESC")
brak, zgodne, rozne = Counter(), 0, Counter()
for ref, matref in cur.fetchall():
    czesci = str(ref).split("_")
    if len(czesci) < 2:
        continue
    gat = czesci[1]
    nasz = material_lantek(gat)
    if nasz is None:
        brak[gat] += 1
    elif matref and nasz.upper() != str(matref).strip().upper():
        rozne[(gat, nasz, str(matref).strip())] += 1
    else:
        zgodne += 1
print("\n### 4000 ostatnich blach z bazy: gatunek z referencji vs MatRef produktu")
print("   zgodnych                :", zgodne)
print("   gatunek bez mapowania   :", sum(brak.values()), dict(brak.most_common(15)))
print("   mapowanie != MatRef     :", sum(rozne.values()))
for (gat, nasz, faktyczny), n in rozne.most_common(15):
    print("      '%s' -> mapujemy '%s', a w bazie '%s'  (%d razy)" % (gat, nasz, faktyczny, n))
