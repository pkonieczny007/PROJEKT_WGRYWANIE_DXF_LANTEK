# -*- coding: utf-8 -*-
"""XML mowil 2 operacje - ile naprawde wpadlo do bazy? (tylko SELECT)

To rozstrzyga, czy tor XML potrafi wgrac marszrute laser+giecie.
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import lantek_db as db

KAT = Path(r"C:\Lantek\importxml")
PLIKI = ["SheetParts_2026-09-18_110142.xml", "SheetParts_2025-12-16_071116.xml",
         "SheetParts_2025-12-15_125220.xml", "SheetParts_2025-12-04_134205.xml",
         "SheetParts_2025-11-13_132821.xml", "SheetParts_2026-03-05_111237.xml",
         "SheetParts_2026-02-19_115947.xml"]


def ops_z_xml(p: Path):
    t = p.read_text(encoding="cp1250", errors="replace")
    ops = defaultdict(list)
    for m in re.finditer(r'TblRef="PRODUCT OPERATIONS">(.*?)</COMMAND>', t, re.S):
        b = m.group(1)
        ref = re.search(r'"PrdRef" FldValue="([^"]*)"', b).group(1)
        ops[ref].append((int(re.search(r'"OOrder" FldValue="([^"]*)"', b).group(1)),
                         re.search(r'"OprRef" FldValue="([^"]*)"', b).group(1)))
    return ops


cn = db.polacz(Config.DB)
print("%-38s %5s %6s %6s %6s  %s" % ("plik XML", "czesc", "2ops", "wbazie", "2wbaz", "werdykt"))
print("-" * 104)
for nazwa in PLIKI:
    p = KAT / nazwa
    if not p.is_file():
        print("%-38s BRAK PLIKU" % nazwa)
        continue
    ops = ops_z_xml(p)
    wiele = {r: o for r, o in ops.items() if len(o) > 1}
    if not wiele:
        print("%-38s %5d %6d  (w XML nikt nie ma 2 operacji)" % (nazwa, len(ops), 0))
        continue
    refy = list(wiele)[:300]
    w_bazie = db.operacje_po_ref(cn, refy)
    jest = [r for r in refy if r in w_bazie]
    dwa = [r for r in refy if len(w_bazie.get(r, [])) > 1]
    werdykt = "OK - marszruta wchodzi" if len(dwa) == len(jest) and jest else \
              ("BRAK DRUGIEJ OPERACJI" if jest else "produktow nie ma w bazie")
    print("%-38s %5d %6d %6d %6d  %s" %
          (nazwa, len(ops), len(wiele), len(jest), len(dwa), werdykt))
    for r in refy[:3]:
        print("        %-42s XML: %-22s BAZA: %s" %
              (r[:42], " -> ".join(o[1] for o in sorted(wiele[r])),
               db.marszruta_txt(w_bazie.get(r, [])) or "(brak)"))
