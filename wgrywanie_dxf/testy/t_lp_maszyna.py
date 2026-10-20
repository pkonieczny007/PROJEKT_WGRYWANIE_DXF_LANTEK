# -*- coding: utf-8 -*-
"""LP (lewy+prawy), duplikaty, wybor maszyny, edycja referencji, drugi import
poprawki marszruty. BEZ wgrywania do LANTEKA (atrapa importu), z bazy tylko SELECT.

    python testy/t_lp_maszyna.py [NUMER]
"""
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TMP = Path(tempfile.gettempdir()) / "test_wgrywanie_dxf_lp"
shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir()
os.environ["LANTEK_DXF_DIR"] = str(TMP / "DXF")
os.environ["DATA_DIR"] = str(TMP / "data")
os.environ["REJESTR_ZRODEL_DIR"] = str(TMP / "rejestr_zrodel")   # NIE prawdziwy na QNAP

from app import app  # noqa: E402
from services import powersync  # noqa: E402

NUMER = sys.argv[1] if len(sys.argv) > 1 else "82_1129"
T = "//qnap-energo/Technologia/2026/82_1129/"
WYKAZ = T + "ROBOCZY_6FB+3FB_82.45681129_lista mateiałowa akt.12.09.2026(6FB+3FB).xlsm"
FOLDERY = [T + "AGA technologia/DXF82/DXF_do_wgrania",
           T + "AGA technologia/DXF_do_wgrania_cz2/DXF_do_wgrania"]


class Atrapa:
    udany = uruchomiony = True
    polecen = ok = 1
    ostrzezen = bledow = 0
    czas_s = 0.1
    log = None
    komunikaty = []
    polecenie = ["atrapa"]

    def podsumowanie(self):
        return "ATRAPA - nic nie wgrano"


wywolan = []
powersync.wgraj = lambda *a, **k: (wywolan.append(str(a[0])), Atrapa())[1]
c = app.test_client()
OK_ALL = True


def sprawdz(opis, warunek):
    global OK_ALL
    OK_ALL &= bool(warunek)
    print("  [%s] %s" % ("OK " if warunek else "ZLE", opis))


def stan():
    with c.session_transaction() as s:
        return json.loads((Path(s["folder"]) / "stan.json").read_text(encoding="utf-8"))


if not Path(WYKAZ).is_file():
    import glob
    WYKAZ = glob.glob(T + "ROBOCZY_*.xls*")[0]
print("wykaz:", WYKAZ)

c.post("/dxf/", data={"akcja": "kontrola", "numer": NUMER, "wykaz": WYKAZ,
                      "folder_dxf": FOLDERY, "ordref": NUMER + "_BLACHY", "badaj_dxf": ""})
c.post("/dxf/przebieg", data={"akcja": "kontrola"})
st = stan()
k = st["kontrola"]
print("\n1. LP i bilans:", k["bilans"])
lp = [p for p in st["podglad"] if p["strona"]]
sprawdz("wiersze LP rozbite na L i P (%d elementow)" % len(lp), lp and len(lp) % 2 == 0)
bez_dxf = [p["ref"] for p in lp if p["stan_dxf"] == "brak"]
# znany rozjazd w danych 82_1129: ..._42016_..._LP_1 ma pliki _L_1 i _P_2 (nie _P_1)
print("     bez pliku:", bez_dxf)
sprawdz("elementy L/P maja swoje pliki DXF (bez pliku: %d)" % len(bez_dxf), len(bez_dxf) <= 1)
if lp:
    print("     np.", lp[0]["ref_wykaz"], "->", lp[0]["ref"], "ilosc", lp[0]["ilosc"])
sprawdz("bilans: wiersze + LP = oczekiwane",
        k["bilans"]["oczekiwanych"] == k["bilans"]["wierszy"] + k["bilans"]["lp"])

print("\n2. maszyna")
z_ref = [p for p in st["podglad"] if p["ref"]]
grube = [p for p in z_ref if (p["grubosc"] or 0) >= 20]
cienkie = [p for p in z_ref if (p["grubosc"] or 0) < 20]
sprawdz("od 20 mm plazma (%d poz.)" % len(grube), all(p["maszyna"] == "plazma" for p in grube))
sprawdz("ponizej 20 mm laser (%d poz.)" % len(cienkie), all(p["maszyna"] == "laser" for p in cienkie))
pop = [p for p in st["podglad"] if p["popraw_marszrute"]]
print("     do poprawki maszyny:", len(pop), "| np.",
      [(p["ref"], p["maszyna_lantek"], p["maszyna"]) for p in pop[:2]])
grupa = next(m for m in k["materialy"] if m.get("klucz", "").startswith("20|"))

# zmiany: cala grupa 20 mm na laser + jedna pozycja z wyjatkiem i nowa referencja
p0 = cienkie[0]
nowa_ref = p0["ref"].rstrip("_") + "X_"
zmiany = {"grupy": {grupa["klucz"]: "laser"},
          "pozycje": {p0["ref_dxf"]: {"ref": nowa_ref, "maszyna": "plazma"}}}
c.post("/dxf/przebieg", data={"akcja": "zmiany", "zmiany_json": json.dumps(zmiany)})
st = stan()
w20 = [p for p in st["podglad"] if p["ref"] and p["klucz_grupy"] == grupa["klucz"]]
sprawdz("grupa %s po zmianie na laser" % grupa["klucz"],
        w20 and all(p["maszyna"] == "laser" for p in w20))
p1 = next(p for p in st["podglad"] if p["ref_dxf"] == p0["ref_dxf"])
sprawdz("wyjatek pozycji: plazma, referencja %s" % p1["ref"],
        p1["maszyna"] == "plazma" and p1["ref"] == nowa_ref and p1["stan_dxf"] != "brak")

j = c.get("/dxf/api/ref?ref=" + p0["ref"]).get_json()
sprawdz("api: istniejaca referencja rozpoznana (w bazie=%s)" % j["w_bazie"], j["w_bazie"] is not None)
j = c.get("/dxf/api/ref?ref=TEST_NIE_MA_TAKIEJ_9999").get_json()
sprawdz("api: wolna referencja", j["w_bazie"] is False)

print("\n2b. reczna zmiana gatunku (z INTEGRY), grubosci, ilosci i ruty")
k = st["kontrola"]
sprawdz("listy z INTEGRY: %d materialow, %d rut" % (len(k["matrefy"]), len(k["ruty"])),
        k["matrefy"] and any(r["ref"] == "P+G" for r in k["ruty"]))
p2 = cienkie[1]
inny_mat = next(m for m in k["matrefy"] if m != p2["material"])
# nowa (wolna) referencja - stara jest w bazie z innym materialem, wiec bez niej
# kontrola dalaby STOP ELEMENT_INNY_W_BAZIE (i slusznie)
zmiany["pozycje"][p2["ref_dxf"]] = {"material": inny_mat, "grubosc": "13", "ilosc": "7",
                                    "ruta": "P+G", "ref": p2["ref"].rstrip("_") + "Y_"}
zmiany["pozycje"]["NIE_MA"] = {"material": "WYMYSLONY_MATERIAL"}
c.post("/dxf/przebieg", data={"akcja": "zmiany", "zmiany_json": json.dumps(zmiany)})
st = stan()
q = next(p for p in st["podglad"] if p["ref_dxf"] == p2["ref_dxf"])
sprawdz("material %s, grubosc %s, ilosc %s, ruta %s, maszyna %s"
        % (q["material"], q["grubosc"], q["ilosc"], q["ruta_reczna"], q["maszyna"]),
        q["material"] == inny_mat and q["grubosc"] == 13 and q["ilosc"] == 7
        and q["ruta_reczna"] == "P+G" and q["maszyna"] == "plazma")
sprawdz("zapamietane 'bylo': %s" % q["reczne"], set(q["reczne"]) == {"material", "grubosc", "ilosc"})
sprawdz("material spoza INTEGRY odrzucony", "NIE_MA" not in (st.get("poprawki") or {}))
sprawdz("poprzednie zmiany zostaly (grupa + wyjatek)",
        p0["ref_dxf"] in st["poprawki"] and st["maszyny_grup"].get(grupa["klucz"]) == "laser")

print("\n2c. checkbox - pozycja wylaczona recznie nie idzie do LANTEKA")
p3 = cienkie[2]
zmiany["pozycje"][p3["ref_dxf"]] = {"wylacz": True}
c.post("/dxf/przebieg", data={"akcja": "zmiany", "zmiany_json": json.dumps(zmiany)})
st = stan()
q3 = next(p for p in st["podglad"] if p["ref_dxf"] == p3["ref_dxf"])
sprawdz("wylaczona: w podgladzie zostaje, w do_wgrania jej nie ma",
        q3["wylaczona"] and p3["ref"] not in {p["ref"] for p in st["do_wgrania"]})
sprawdz("bilans: wylaczonych %s" % st["kontrola"]["bilans"].get("wylaczonych"),
        st["kontrola"]["bilans"].get("wylaczonych") == 1)
sprawdz("pozostale zmiany reczne zostaly", p2["ref_dxf"] in st["poprawki"])

print("\n3. XML + poprawka marszruty")
c.post("/dxf/przebieg", data={"akcja": "xml"})
x = stan()["xml"]
sprawdz("plik poprawki marszruty (%s pozycji)" % x.get("marszrut_do_poprawy"), x.get("xml_marszruta"))
tresc = Path(x["xml_marszruta"]).read_bytes().decode("cp1250")
sprawdz("poprawka ma plazme dla wyjatku",
        re.search(r'Value="%s".*?Stigal' % re.escape(nowa_ref), tresc, re.S) is not None)
glowny = Path(x["xml"]).read_bytes().decode("cp1250")
sprawdz("glowny XML: nowa referencja, plik DXF ze starej nazwy",
        'FldValue="%s"' % nowa_ref in glowny)
blok = re.search(r'FldRef="PrdRef" FldValue="%s".*?</COMMAND>' % re.escape(q["ref"]), glowny, re.S)
sprawdz("glowny XML: reczny material i grubosc 13",
        blok and 'FldValue="%s"' % inny_mat in blok.group(0) and 'FldValue="13"' in blok.group(0))
ops = [(re.search(r'"WrkRef" FldValue="([^"]*)"', b).group(1),
        re.search(r'"OprRef" FldValue="([^"]*)"', b).group(1))
       for b in re.findall(r'<COMMAND Name="Import" TblRef="PRODUCT OPERATIONS">(.*?)</COMMAND>',
                           tresc, re.S)
       if 'FldValue="%s"' % q["ref"] in b]
sprawdz("poprawka: ruta P+G = plazma + giecie (%s)" % ops, ops and ops[0][0].startswith("Stigal")
        and any(o[1] == "Giecie" for o in ops))

print("\n4. wgranie: glowny + poprawka (atrapa)")
r = c.post("/dxf/przebieg", data={"akcja": "wgraj", "potwierdzam": "on", "ponownie": "on",
                                  "haslo": NUMER + "_BLACHY"}, follow_redirects=True)
sprawdz("dwa importy: glowny, potem marszruta (%s)" % [Path(w).name for w in wywolan],
        len(wywolan) == 2 and "Marszruta_" in wywolan[1])
sprawdz("stan: wynik poprawki zapisany", (stan().get("wgranie") or {}).get("marszruta"))

print("\nWYNIK:", "OK" if OK_ALL else "SA BLEDY")
sys.exit(0 if OK_ALL else 1)
