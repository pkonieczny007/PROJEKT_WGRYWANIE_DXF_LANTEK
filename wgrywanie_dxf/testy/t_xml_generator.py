# -*- coding: utf-8 -*-
"""Porownanie: nasz XML kontra realny XML makra (SheetParts_2026-09-18_111617.xml).

Te same 14 elementow. Struktura ma byc identyczna; roznice maja byc WYLACZNIE tam,
gdzie makro jest bledne: puste UData8 i recznie wpisywane operacje.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.xml_sheetparts import ElementXML, zbuduj, podsumowanie  # noqa: E402

WZORZEC = Path(r"..\kontekst\wykaz\SheetParts_2026-09-18_111617.xml")
WZORZEC = (Path(__file__).resolve().parent.parent.parent / "kontekst" / "wykaz" /
           "SheetParts_2026-09-18_111617.xml")

# --- dane jak w realnym wgraniu (referencje 1:1 z wykazu 82_1129)
DANE = [
    ("12_S235_SL40033136_p1_1st_G_1129_", 12, 1),
    ("8_S235_SL40033947_p1_2st__1129_", 8, 2),
    ("5_S235_SL40034102_p2_1st_GS_1129_L", 5, 1),
    ("12_S235_SL40034102_p5_1st_GS_1129_L", 12, 1),
    ("12_S235_SL40034102_p7_1st_GS_1129_L", 12, 1),
    ("5_S235_SL40034102_p9_1st_GS_1129_L", 5, 1),
    ("12_S235_SL40034102_p10_1st_S_1129_", 12, 1),
    ("12_S235_SL40034102_p11_1st_S_1129_", 12, 1),
    ("5_S235_SL40034102_p1_1st_GS_1129_P", 5, 1),
    ("12_S235_SL40034102_p3_1st_S_1129_1", 12, 1),
    ("12_S235_SL40034102_p4_1st_GS_1129_P", 12, 1),
    ("12_S235_SL40034102_p6_1st_GS_1129_P", 12, 1),
    ("5_S235_SL40034102_p8_1st_GS_1129_P", 5, 1),
    ("12_S235_SL40034102_p10_1st_S_1129_1", 12, 1),
]
ORD = "12_7453_BLACHY-test"
KAT = r"C:\Lantek\importxml\DXF"

elementy = [ElementXML(ref=r, material="S235JR", grubosc=g, ilosc=il,
                       dxf="%s\\%s.DXF" % (KAT, r)) for r, g, il in DANE]
nasz = zbuduj(elementy, ordref=ORD, zaloz_zamowienie=True, pierwsza_linia=1)
print("podsumowanie:", podsumowanie(elementy, ORD, True))

wzor = WZORZEC.read_text(encoding="cp1250", errors="replace")


def struktura(txt):
    return [(m.group(1), tuple(re.findall(r'FldRef="([^"]+)"', m.group(2))))
            for m in re.finditer(r'<COMMAND Name="Import" TblRef="([^"]+)">(.*?)</COMMAND>',
                                 txt, re.S)]


s_nasz, s_wzor = struktura(nasz), struktura(wzor)
print("\npolecen: nasz=%d wzorzec=%d" % (len(s_nasz), len(s_wzor)))

kol_nasz = [t for t, _ in s_nasz]
kol_wzor = [t for t, _ in s_wzor]
print("kolejnosc tabel zgodna:", kol_nasz == kol_wzor)
if kol_nasz != kol_wzor:
    print("   nasz   :", kol_nasz[:12])
    print("   wzorzec:", kol_wzor[:12])

pola_nasz = {t: p for t, p in s_nasz}
pola_wzor = {t: p for t, p in s_wzor}
print("\npola w kazdej tabeli:")
for t in dict.fromkeys(kol_wzor):
    zg = pola_nasz.get(t) == pola_wzor.get(t)
    print("   %-20s %s" % (t, "identyczne" if zg else "ROZNE"))
    if not zg:
        print("      nasz   :", pola_nasz.get(t))
        print("      wzorzec:", pola_wzor.get(t))

# roznice wartosci UData8
u_nasz = re.findall(r'FldRef="UData8" FldValue="([^"]*)"', nasz)
u_wzor = re.findall(r'FldRef="UData8" FldValue="([^"]*)"', wzor)
print("\nUData8 - nasz niepuste: %d/%d | wzorzec niepuste: %d/%d"
      % (sum(1 for x in u_nasz if x), len(u_nasz),
         sum(1 for x in u_wzor if x), len(u_wzor)))

# grubosci
h_nasz = re.findall(r'FldRef="Height" FldValue="([^"]*)"', nasz)
h_wzor = re.findall(r'FldRef="Height" FldValue="([^"]*)"', wzor)
print("Height nasz   :", h_nasz)
print("Height wzorzec:", h_wzor)

# koncowka i kodowanie
print("\nkonczy sie </DATAEX>:", nasz.rstrip().endswith("</DATAEX>"))
print("CRLF:", "\r\n" in nasz, "| daje sie zapisac cp1250:", bool(nasz.encode("cp1250")))

print("\n--- pierwszy element naszego XML ---")
print("\n".join(nasz.split("\r\n")[:24]))
