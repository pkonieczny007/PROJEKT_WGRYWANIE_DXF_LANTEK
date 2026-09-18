# -*- coding: utf-8 -*-
"""Kontrola przed wgraniem na realnym zleceniu - bez wgrywania czegokolwiek."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import Config
from services import kontrola, lantek_db as db, raport, ruty, wykaz as W
from services import zlecenie as Z

NUMER = sys.argv[1] if len(sys.argv) > 1 else "82_1129"
FOLDER_DXF = sys.argv[2] if len(sys.argv) > 2 else None

t0 = time.time()
prop = Z.propozycje(NUMER, Config.KORZENIE_TECHNOLOGIA, Config.KORZENIE_DXF,
                    Config.GLEBOKOSC_SKANU)
wykaz_plik = prop["wykazy"][0]["sciezka"] if prop["wykazy"] else None
folder_dxf = [FOLDER_DXF] if FOLDER_DXF else [d["sciezka"] for d in prop["foldery_dxf"][:3]]
print("zlecenie   :", NUMER)
print("wykaz      :", wykaz_plik)
print("foldery DXF:")
[print("   ", f) for f in folder_dxf]
print("ordref     :", prop["ordref"], " (%.1f s)" % (time.time() - t0))
if not wykaz_plik or not folder_dxf:
    sys.exit("brak wykazu albo folderu DXF")

wyk = W.wczytaj(wykaz_plik)
print("\nwykaz: %d wierszy, %d pozycji BLACHA, kolumna referencji '%s', ilosc '%s'"
      % (wyk.wierszy, wyk.blacha, wyk.kolumna_nazwy, wyk.kolumna_ilosci))

# kolumna referencji wg trafien w pliki DXF
from services import dxf_check as dx
mapa = {}
for _f in folder_dxf:
    for _k, _v in dx.zbierz(_f).items():
        mapa.setdefault(_k, []).extend(_v)
kand = W.kandydaci_nazwy_wg_dxf(wykaz_plik, {p.stem for v in mapa.values() for p in v})
print("kandydaci na kolumne referencji:")
for k in kand:
    print("   %-22s trafien %4d / wypelnionych %4d" % (k["kolumna"], k["trafien"], k["wypelnionych"]))
najlepsza = kand[0]["kolumna"] if kand and kand[0]["trafien"] else None
if najlepsza and najlepsza != wyk.kolumna_nazwy:
    print("-> biore kolumne '%s'" % najlepsza)
    wyk = W.wczytaj(wykaz_plik, kolumna_nazwy=najlepsza)

cn = None
try:
    cn = db.polacz(Config.DB)
except Exception as e:
    print("baza niedostepna:", e)

t1 = time.time()
wynik = kontrola.przed(wyk, folder_dxf, prop["ordref"], cn=cn,
                       szablony_rut=ruty.wczytaj_z_bazy(cn) if cn else None)
print("\nkontrola: %.1f s" % (time.time() - t1))
print("WERDYKT:", wynik.werdykt, "| licznik:", wynik.licznik(),
      "| do wgrania:", len(wynik.do_wgrania))
print("kody:", wynik.kody())
print("sierot (pliki spoza wykazu):", len(wynik.sieroty))
print("pierwsza wolna linia zamowienia:", wynik.pierwsza_linia)

print("\npierwsze 12 pozycji:")
for w in wynik.wiersze[:12]:
    print("  %-6s w.%-4d %-38s %-7s gr=%-5s kod=%-4s ruta=%-6s %-18s dxf=%s"
          % (w.poziom, w.poz.wiersz, w.ref[:38], w.material, w.poz.grubosc,
             w.kod, w.ruta, w.marszruta, w.stan_dxf))
    for u in w.uwagi:
        print("         %s %s: %s" % (u.poziom, u.kod, u.opis[:120]))

folder = Z.folder_przebiegu(Config.DATA_DIR, NUMER)
pliki = raport.zapisz_przed(wynik, folder, tytul_dodatkowy=Path(wykaz_plik).name)
print("\nraport:", pliki["html"])
