# -*- coding: utf-8 -*-
"""Buduje maly zestaw probny do przetestowania calego toru, lacznie z wgraniem.

Powstaje folder testy/zestaw_probny/ z:
  * wykaz_probny.xlsx - 2 pozycje BLACHA (jedna gieta, jedna nie),
  * dxf/              - 2 pliki DXF pod nazwami referencji.

Referencje maja przedrostek TESTAI i zlecenie 9999, zeby bylo widac w bazie,
ze to proba, i zeby nie kolidowaly z niczym prawdziwym.
"""
import shutil
import sys
from pathlib import Path

import openpyxl

KAT = Path(__file__).resolve().parent / "zestaw_probny"
DXF_ZRODLO = Path(r"C:\Lantek\importxml\DXF")

POZYCJE = [
    # (referencja, grubosc, gatunek, ilosc, kod technologii, Zeinr, Posn)
    ("10_S235_TESTAI_p1_1st_G_9999_", 10, "S235", 1, "G", "TESTAI", 1),
    ("10_S235_TESTAI_p2_2st_S_9999_", 10, "S235", 2, "S", "TESTAI", 2),
]

NAGLOWKI = ["L.P.", "Posn", "Zeinr", "Anz.", "Bezeichnung.............................",
            "ZAKUPY", "Nazwa", "Gięcie", "INDEX", "sprawdzenie", "propozycja",
            "gatunek_poprawiony", "grubosc_poprawiona"]


def main():
    KAT.mkdir(parents=True, exist_ok=True)
    kat_dxf = KAT / "dxf"
    kat_dxf.mkdir(exist_ok=True)

    zrodla = sorted(p for p in DXF_ZRODLO.glob("*.dxf") if p.is_file())
    if len(zrodla) < 2:
        sys.exit("brak plikow DXF do skopiowania w %s" % DXF_ZRODLO)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "WYKAZ"
    ws.append(NAGLOWKI)
    for i, (ref, gr, gat, il, kod, zeinr, posn) in enumerate(POZYCJE):
        ws.append([i + 1, posn, zeinr, il,
                   "BLECH*%03d,00*EN 10029*1.0038*%s" % (gr, gat),
                   "BLACHA", ref, kod, "", "proba", "", gat, gr])
        docelowy = kat_dxf / ("%s.dxf" % ref)
        shutil.copy2(zrodla[i % len(zrodla)], docelowy)
    plik = KAT / "wykaz_probny.xlsx"
    wb.save(plik)

    print("wykaz     :", plik)
    print("folder DXF:", kat_dxf)
    for p in sorted(kat_dxf.iterdir()):
        print("   %s  (%d B)" % (p.name, p.stat().st_size))
    print("\nW aplikacji wpisz numer zlecenia 'TEST_9999', wklej te dwie sciezki")
    print("recznie i uruchom kontrole. Zamowienie zostaw puste albo TEST_9999_BLACHY.")


if __name__ == "__main__":
    main()
