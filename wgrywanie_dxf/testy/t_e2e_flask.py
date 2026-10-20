# -*- coding: utf-8 -*-
"""Przejscie przez aplikacje: kontrola -> XML. BEZ wgrywania do LANTEKA.

Katalog DXF LANTEKA podmieniony na tymczasowy, zeby nic nie ruszac w C:\\Lantek.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TMP = Path(tempfile.gettempdir()) / "test_wgrywanie_dxf"
TMP.mkdir(exist_ok=True)
os.environ["LANTEK_DXF_DIR"] = str(TMP / "DXF")
os.environ["DATA_DIR"] = str(TMP / "data")

from app import app  # noqa: E402

NUMER = sys.argv[1] if len(sys.argv) > 1 else "82_1129"
FOLDER = sys.argv[2] if len(sys.argv) > 2 else None

app.config["TESTING"] = True
c = app.test_client()

# 1. propozycje
r = c.post("/dxf/", data={"akcja": "propozycje", "numer": NUMER}, follow_redirects=True)
print("propozycje:", r.status_code)
with c.session_transaction() as s:
    pid = s.get("prop_id")
plik_prop = Path(os.environ["DATA_DIR"]) / "_propozycje" / ("%s.json" % pid)
prop = json.loads(plik_prop.read_text(encoding="utf-8")) if pid else {}
print("  folder zlecenia:", prop.get("folder"))
print("  wykazow:", len(prop.get("wykazy", [])), "| folderow DXF:", len(prop.get("foldery_dxf", [])))
if not prop.get("wykazy"):
    sys.exit("brak wykazu - przerwane")

wykaz = prop["wykazy"][0]["sciezka"]
foldery = [FOLDER] if FOLDER else [d["sciezka"] for d in prop["foldery_dxf"][:2]]

# 2. kontrola
r = c.post("/dxf/", data={
    "akcja": "kontrola", "numer": NUMER, "wykaz": wykaz,
    "folder_dxf": foldery, "ordref": prop.get("ordref", ""),
    "badaj_dxf": "", "tryb_ilosci": "pierwszy",
    "wymus_marszrute": "on",
}, follow_redirects=True)
print("\nustawienia zapisane:", r.status_code)

r = c.post("/dxf/przebieg", data={"akcja": "kontrola"}, follow_redirects=True)
print("kontrola:", r.status_code)
with c.session_transaction() as s:
    folder = Path(s["folder"])
st = json.loads((folder / "stan.json").read_text(encoding="utf-8"))
k = st["kontrola"]
print("  werdykt:", k["werdykt"], "| licznik:", k["licznik"])
print("  do wgrania:", len(st["do_wgrania"]))
print("  bez gietarki mimo kodu G:", k["bez_giecia_a_powinno"])
print("  raport:", k["raport"])

# 3. XML
r = c.post("/dxf/przebieg", data={"akcja": "xml"}, follow_redirects=True)
print("\nXML:", r.status_code)
st = json.loads((folder / "stan.json").read_text(encoding="utf-8"))
x = st.get("xml") or {}
print("  plik:", x.get("xml"))
print("  podsumowanie:", x.get("podsumowanie"))
print("  skopiowanych DXF:", x.get("skopiowanych_dxf"), "->", x.get("katalog_dxf"))
if x.get("xml_marszruta"):
    print("  poprawka marszruty:", x["marszrut_do_poprawy"], "pozycji ->", x["xml_marszruta"])

# 4. weryfikacja wygenerowanego pliku
if x.get("xml"):
    tresc = Path(x["xml"]).read_bytes().decode("cp1250")
    prod = re.findall(r'TblRef="PRODUCTS">\s*<FIELD FldRef="PrdRef" FldValue="([^"]*)"', tresc)
    ud8 = re.findall(r'FldRef="UData8" FldValue="([^"]*)"', tresc)
    geo = re.findall(r'FldRef="GeometryPath" FldValue="([^"]*)"', tresc)
    linie = re.findall(r'FldRef="LineNum" FldValue="([^"]*)"', tresc)
    print("\n  produktow w XML   :", len(prod))
    print("  UData8 wypelnione :", sum(1 for u in ud8 if u), "/", len(ud8))
    print("  UData8 == PrdRef  :", all(u == p for u, p in zip(ud8, prod)))
    print("  sciezek geometrii :", len(geo), "| przyklad:", geo[0] if geo else "-")
    print("  wszystkie DXF sa  :", all(Path(g).is_file() for g in geo))
    print("  linie zamowienia  :", len(linie), "| unikalne:", len(set(linie)))
    print("  konczy sie DATAEX :", tresc.rstrip().endswith("</DATAEX>"))
print("\nfolder przebiegu:", folder)
print("pliki:", sorted(p.name for p in folder.iterdir()))
