# -*- coding: utf-8 -*-
"""Test parsera wykazu na przykladzie z kontekstu (82_1129)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.wykaz import wczytaj, kandydaci_nazwy_wg_dxf  # noqa: E402

PLIK = (Path(__file__).resolve().parent.parent.parent / "kontekst" / "wykaz" /
        "przyklad_ROBOCZY_6FB+3FB_82.45681129_lista mateiałowa akt.12.09.2026(6FB)"
        "+REV.A + DOMÓWIENIA akt.16.09.2026.xlsx")

w = wczytaj(PLIK)
print("plik      :", Path(w.plik).name)
print("zakladka  :", w.zakladka, "| wiersz naglowka:", w.wiersz_naglowka)
print("wierszy   :", w.wierszy, "| BLACHA:", w.blacha, "| puste formuly:", w.formuly_puste)
print("kol.nazwy :", w.kolumna_nazwy, "| kol.ilosci:", w.kolumna_ilosci)
print("kandydaci :", list(w.kandydaci_nazwy))
print("kolumny   :", {k: v for k, v in w.kolumny.items() if v is not None})
print("-" * 110)
print("%-4s %-38s %-5s %-5s %-6s %-7s %-5s %-5s %s" %
      ("w.", "referencja", "kolG", "refG", "grub", "gat", "il", "ilRef", "sprawdzenie"))
for p in w.pozycje:
    print("%-4d %-38s %-5s %-5s %-6s %-7s %-5s %-5s %s" %
          (p.wiersz, p.ref, p.kod_kolumna, p.kod_ref, p.grubosc, p.gatunek,
           p.ilosc, p.ilosc_ref, p.sprawdzenie))

# te same 14 referencji, ktore poszly do LANTEKA przez makro
XML14 = """12_S235_SL40033136_p1_1st_G_1129_
8_S235_SL40033947_p1_2st__1129_
5_S235_SL40034102_p2_1st_GS_1129_L
12_S235_SL40034102_p5_1st_GS_1129_L
12_S235_SL40034102_p7_1st_GS_1129_L
5_S235_SL40034102_p9_1st_GS_1129_L
12_S235_SL40034102_p10_1st_S_1129_
12_S235_SL40034102_p11_1st_S_1129_
5_S235_SL40034102_p1_1st_GS_1129_P
12_S235_SL40034102_p3_1st_S_1129_1
12_S235_SL40034102_p4_1st_GS_1129_P
12_S235_SL40034102_p6_1st_GS_1129_P
5_S235_SL40034102_p8_1st_GS_1129_P
12_S235_SL40034102_p10_1st_S_1129_1""".split()
print("-" * 110)
ref_wykaz = [p.ref for p in w.pozycje]
print("w wykazie, brak w XML:", [r for r in ref_wykaz if r not in XML14])
print("w XML, brak w wykazie:", [r for r in XML14 if r not in ref_wykaz])
print("duplikaty referencji :", sorted({r for r in ref_wykaz if ref_wykaz.count(r) > 1}))
print("-" * 110)
for k in kandydaci_nazwy_wg_dxf(PLIK, set(XML14)):
    print(k)
