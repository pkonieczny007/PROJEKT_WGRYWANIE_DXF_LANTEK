# -*- coding: utf-8 -*-
"""Skad bierzemy grubosc i gatunek - i czy zrodla sie zgadzaja.

Porownuje trzy zrodla dla kazdej pozycji BLACHA:
  A) kolumny kontrolne wykazu: grubosc_poprawiona / gatunek_poprawiony
  B) czlony referencji:        {grubosc}_{gatunek}_{Zeinr}_...
  C) rozbicie 'Bezeichnung':   BLECH*012,00*EN 10029*1.0122*S235JRC
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import wykaz as W          # noqa: E402
from services.kontrola import material_lantek  # noqa: E402
from services.wspolne import do_liczby   # noqa: E402

PLIK = sys.argv[1] if len(sys.argv) > 1 else (
    "//QNAP-ENERGO/Technologia/2026/82_1129/ROBOCZY_6FB+3FB_82.45681129_"
    "lista mateiałowa akt.12.09.2026(6FB)+REV.A + DOMÓWIENIA akt.16.09.2026.xlsx")
KOL = sys.argv[2] if len(sys.argv) > 2 else None

w = W.wczytaj(PLIK, kolumna_nazwy=KOL)
print("wykaz:", Path(w.plik).name)
print("pozycji BLACHA:", w.blacha, "| kolumna referencji:", w.kolumna_nazwy)
print("kolumny: grubosc ->", w.kolumny.get("grubosc"),
      "| gatunek ->", w.kolumny.get("gatunek"),
      "| bezeichnung ->", w.kolumny.get("bezeichnung"))

licz = Counter()
przyklady = {"gr_rozjazd": [], "gat_rozjazd": [], "gr_brak": [], "gat_brak": [],
             "gat_bez_mapowania": []}

for p in w.pozycje:
    if not p.ref:
        licz["bez referencji"] += 1
        continue
    czesci = p.ref.split("_")
    gr_ref = do_liczby(czesci[0]) if czesci else None
    gat_ref = czesci[1] if len(czesci) > 1 else ""

    # grubosc
    if p.grubosc is None:
        licz["grubosc: brak w kolumnie"] += 1
        przyklady["gr_brak"].append(p.ref)
    elif gr_ref is not None and abs(gr_ref - p.grubosc) > 0.001:
        licz["grubosc: kolumna != referencja"] += 1
        przyklady["gr_rozjazd"].append("%s: kolumna %s, referencja %s"
                                       % (p.ref, p.grubosc, gr_ref))
    else:
        licz["grubosc: zgodna"] += 1

    # gatunek
    if not p.gatunek:
        licz["gatunek: brak w kolumnie"] += 1
        przyklady["gat_brak"].append(p.ref)
    elif gat_ref and p.gatunek.replace(" ", "").upper() != gat_ref.replace(" ", "").upper():
        licz["gatunek: kolumna != referencja"] += 1
        przyklady["gat_rozjazd"].append("%s: kolumna '%s', referencja '%s'"
                                        % (p.ref, p.gatunek, gat_ref))
    else:
        licz["gatunek: zgodny"] += 1

    if p.gatunek and not material_lantek(p.gatunek):
        licz["gatunek: brak mapowania na MatRef"] += 1
        przyklady["gat_bez_mapowania"].append("%s -> '%s'" % (p.ref, p.gatunek))

print()
for k, v in sorted(licz.items()):
    print("  %-38s %5d" % (k, v))

for etykieta, klucz in (("grubosc rozjazd", "gr_rozjazd"),
                        ("gatunek rozjazd", "gat_rozjazd"),
                        ("brak grubosci", "gr_brak"),
                        ("brak gatunku", "gat_brak"),
                        ("gatunek bez mapowania", "gat_bez_mapowania")):
    if przyklady[klucz]:
        print("\n%s (%d) - przyklady:" % (etykieta, len(przyklady[klucz])))
        for x in przyklady[klucz][:8]:
            print("   ", x)

# jakie gatunki w ogole wystepuja
gat = Counter(p.gatunek for p in w.pozycje if p.ref)
print("\ngatunki w kolumnie:", dict(gat.most_common(12)))
gat_ref = Counter(p.ref.split("_")[1] for p in w.pozycje if p.ref and "_" in p.ref)
print("gatunki w referencji:", dict(gat_ref.most_common(12)))
