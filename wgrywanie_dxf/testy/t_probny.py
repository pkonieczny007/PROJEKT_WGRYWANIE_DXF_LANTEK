# -*- coding: utf-8 -*-
"""Kontrola + XML na zestawie probnym. Nic nie wgrywa."""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import kontrola, lantek_db as db, ruty, wykaz as W, xml_sheetparts as X

KAT = Path(__file__).resolve().parent / "zestaw_probny"
wyk = W.wczytaj(KAT / "wykaz_probny.xlsx")
print("wykaz: %d wierszy, %d BLACHA, kolumna '%s'" % (wyk.wierszy, wyk.blacha, wyk.kolumna_nazwy))
cn = db.polacz(Config.DB)
wynik = kontrola.przed(wyk, [str(KAT / "dxf")], "TEST_9999_BLACHY", cn=cn,
                       szablony_rut=ruty.wczytaj_z_bazy(cn))
print("WERDYKT:", wynik.werdykt, "| licznik:", wynik.licznik())
for w in wynik.wiersze:
    print("  %-6s %-34s %-7s gr=%-5s il=%-4s kod=%-3s ruta=%-6s %-18s dxf=%s"
          % (w.poziom, w.ref, w.material, w.poz.grubosc, w.poz.ilosc, w.kod,
             w.ruta, w.marszruta, w.stan_dxf))
    for u in w.uwagi:
        print("        %s %s: %s" % (u.poziom, u.kod, u.opis))

el = [X.ElementXML(ref=w.ref, material=w.material, grubosc=w.poz.grubosc,
                   ilosc=w.poz.ilosc, dxf=str(w.plik_dxf)) for w in wynik.do_wgrania]
tresc = X.zbuduj(el, ordref="TEST_9999_BLACHY", zaloz_zamowienie=True,
                 pierwsza_linia=wynik.pierwsza_linia)
print("\n--- XML (%d znakow) ---" % len(tresc))
print(tresc)
