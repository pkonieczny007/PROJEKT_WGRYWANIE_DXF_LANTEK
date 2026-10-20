# -*- coding: utf-8 -*-
"""Ochrona przed przypadkowym ponownym wgraniem - BEZ wgrywania do LANTEKA.

XmlImporter podmieniony na atrape, katalog DXF i rejestr w katalogu tymczasowym.
Z bazy tylko SELECT. Zlecenie, ktorego elementy juz sa w zamowieniu:

    python testy/t_ponowne_wgranie.py [NUMER] [WYKAZ] [FOLDER_DXF]
"""
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TMP = Path(tempfile.gettempdir()) / "test_wgrywanie_dxf_ponowne"
shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir()
os.environ["LANTEK_DXF_DIR"] = str(TMP / "DXF")
os.environ["DATA_DIR"] = str(TMP / "data")
os.environ["REJESTR_ZRODEL_DIR"] = str(TMP / "rejestr_zrodel")   # NIE prawdziwy na QNAP

from app import app  # noqa: E402
from modules.dxf import routes  # noqa: E402
from services import lantek_db, powersync  # noqa: E402

NUMER = sys.argv[1] if len(sys.argv) > 1 else "37_1731"
T = "//QNAP-ENERGO/Technologia/2026/37_1731/"
WYKAZ = sys.argv[2] if len(sys.argv) > 2 else \
    T + "ROBOCZY_37.45671731_lista materiałowa + rev.A akt.07.10.2026.xlsm"
FOLDER = sys.argv[3] if len(sys.argv) > 3 else T + "AGA technologia/DXF_do_wgrania"
ORDREF = NUMER + "_BLACHY"


class Atrapa:
    """Udaje wynik XmlImporter - nic nie idzie do bazy."""
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
powersync.wgraj = lambda *a, **k: (wywolan.append(a[0]), Atrapa())[1]

c = app.test_client()
OK_ALL = True


def sprawdz(opis, warunek):
    global OK_ALL
    OK_ALL &= bool(warunek)
    print("  [%s] %s" % ("OK " if warunek else "ZLE", opis))


def stan():
    with c.session_transaction() as s:
        return json.loads((Path(s["folder"]) / "stan.json").read_text(encoding="utf-8"))


def flashe(r):
    return re.findall(r'class="flash f-\w+">(.*?)</div>', r.get_data(as_text=True), re.S)


def wgraj(**pola):
    przed = len(wywolan)
    r = c.post("/dxf/przebieg", data=dict(akcja="wgraj", **pola), follow_redirects=True)
    wazne = [f for f in flashe(r) if f.startswith(("PRZERWANE", "Wgranie"))]
    return len(wywolan) > przed, " | ".join(wazne)[:260], r.get_data(as_text=True)


# --- przygotowanie: kontrola
c.post("/dxf/", data={"akcja": "kontrola", "numer": NUMER, "wykaz": WYKAZ,
                      "folder_dxf": [FOLDER], "ordref": ORDREF, "badaj_dxf": ""})
c.post("/dxf/przebieg", data={"akcja": "kontrola"})
st = stan()
powt = [p for p in st["do_wgrania"] if p.get("w_zamowieniach")]
print("kontrola: do wgrania %d, juz w zamowieniach %d"
      % (len(st["do_wgrania"]), len(powt)))
sprawdz("elementy z zamowienia nie sa juz blokowane (STOP), tylko UWAGA", powt)
if not powt:
    sys.exit("zlecenie bez elementow w zamowieniach - podaj inne")

# --- 1. XML domyslny: elementy z zamowienia bez linii
print("\n1. XML domyslny")
c.post("/dxf/przebieg", data={"akcja": "xml"})
x = stan()["xml"]
tresc = Path(x["xml"]).read_bytes().decode("cp1250")
linie_xml = re.findall(r'FldRef="ArtRef" FldValue="([^"]*)"', tresc)
sprawdz("brak linii dla %d powtorek (linii w XML %d)" % (x["powtorek"], len(linie_xml)),
        not set(linie_xml) & {p["ref"] for p in powt})
sprawdz("podwojenie wylaczone", not x["podwojenie"])

print("\n2. drugie wgranie bez swiadomej zgody")
poszlo, f, html = wgraj(potwierdzam="on")
sprawdz("przerwane: %s" % f, not poszlo and "PONOWNE" in f)
sprawdz("strona pokazuje pole do przepisania '%s'" % ORDREF,
        'name="haslo"' in html and "<code>%s</code>" % ORDREF in html)
poszlo, f, _ = wgraj(potwierdzam="on", ponownie="on", haslo="zle")
sprawdz("zle haslo - przerwane", not poszlo)
poszlo, f, _ = wgraj(potwierdzam="on", haslo=ORDREF)
sprawdz("haslo bez checkboxa - przerwane", not poszlo)
poszlo, f, _ = wgraj(potwierdzam="on", ponownie="on", haslo=ORDREF.lower())
sprawdz("checkbox + haslo - poszlo: %s" % f, poszlo)

wpis = json.loads((TMP / "data" / "rejestr_wgran.jsonl").read_text(encoding="utf-8")
                  .splitlines()[-1])
sprawdz("rejestr: ponowne=%s, podwojenie=%s, refy %d"
        % (wpis["ponowne"], wpis["podwojenie"], len(wpis["refy"])),
        wpis["ponowne"] and not wpis["podwojenie"] and wpis["refy"])

print("\n3. podwojenie")
c.post("/dxf/przebieg", data={"akcja": "xml", "podwojenie": "on"})
x = stan()["xml"]
tresc = Path(x["xml"]).read_bytes().decode("cp1250")
linie_xml = re.findall(r'FldRef="ArtRef" FldValue="([^"]*)"', tresc)
sprawdz("XML ma linie dla powtorek (%d linii)" % len(linie_xml),
        {p["ref"] for p in powt} <= set(linie_xml))
poszlo, f, html = wgraj(potwierdzam="on", ponownie="on", haslo=ORDREF)
sprawdz("haslo zamowienia nie wystarcza - trzeba PODWAJAM", not poszlo and "PODWAJAM" in f)
sprawdz("strona ostrzega o podwojeniu", "Z PODWOJENIEM ILOSCI" in html)
poszlo, f, _ = wgraj(potwierdzam="on", ponownie="on", haslo="podwajam")
sprawdz("PODWAJAM - poszlo", poszlo)

print("\n4. dwa klikniecia naraz")
routes._WGRYWANIE.acquire()
try:
    poszlo, f, _ = wgraj(potwierdzam="on", ponownie="on", haslo="PODWAJAM")
finally:
    routes._WGRYWANIE.release()
sprawdz("drugie przerwane: %s" % f, not poszlo and "trwa" in f)

print("\n5. XML nieaktualny (ktos wgral po zbudowaniu)")
c.post("/dxf/przebieg", data={"akcja": "xml"})
st = stan()
st["xml"]["refy_z_linia"] = st["xml"]["refy_z_linia"] + [powt[0]["ref"]]
with c.session_transaction() as s:
    (Path(s["folder"]) / "stan.json").write_text(json.dumps(st), encoding="utf-8")
poszlo, f, _ = wgraj(potwierdzam="on", ponownie="on", haslo=ORDREF)
sprawdz("przerwane: %s" % f, not poszlo and "po zbudowaniu XML" in f)

print("\n6. pierwsze wgranie (nic w bazie, pusty rejestr) - bez dodatkowej zgody")
c.post("/dxf/przebieg", data={"akcja": "xml"})
(TMP / "data" / "rejestr_wgran.jsonl").unlink()
oryg = lantek_db.zamowienia_po_ref
lantek_db.zamowienia_po_ref = lambda cn, refy: {}
st = stan()
st["xml"]["powtorek"] = 0
with c.session_transaction() as s:
    (Path(s["folder"]) / "stan.json").write_text(json.dumps(st), encoding="utf-8")
try:
    poszlo, f, html = wgraj(potwierdzam="on")
finally:
    lantek_db.zamowienia_po_ref = oryg
sprawdz("poszlo z samym 'potwierdzam'", poszlo)

print("\nWYNIK:", "OK" if OK_ALL else "SA BLEDY", "| atrapa wywolana %d razy" % len(wywolan))
sys.exit(0 if OK_ALL else 1)
