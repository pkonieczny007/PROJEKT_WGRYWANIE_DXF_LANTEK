# -*- coding: utf-8 -*-
"""Formularz startowy: podpowiedz folderu i zamowien po numerze, wlasny folder
zlecenia (np. podfolder rewizji), wykaz jako pole z propozycjami.
Tylko odczyt (SELECT z LANTEKA, skan folderow).

    python testy/t_formularz_start.py [NUMER] [FOLDER_ZLECENIA]
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DATA_DIR"] = str(Path(tempfile.gettempdir()) / "test_wgrywanie_dxf" / "data")

from app import app  # noqa: E402

NUMER = sys.argv[1] if len(sys.argv) > 1 else "37_1731"
FOLDER = sys.argv[2] if len(sys.argv) > 2 else \
    "//QNAP-ENERGO/Technologia/2026/37_1731/DXF_37_1731-REWIZJA"

c = app.test_client()

# 1. podpowiedz przy wpisywaniu numeru
j = c.get("/dxf/api/zlecenie?numer=" + NUMER).get_json()
print("api: folder      :", j["folder"])
print("     podfoldery  :", len(j["podfoldery"]))
print("     zamowienia  :", [(z["ordref"], z["linii"], z["max_linia"]) for z in j["zamowienia"]])
print("     lista z     :", j["pobrano"], "| blad:", j["blad"])
assert j["ok"] and j["folder"], "brak folderu zlecenia"
assert c.get("/dxf/api/zlecenie?numer=zle").get_json()["ok"] is False

# 2. "Zaproponuj" z wlasnym folderem zlecenia
r = c.post("/dxf/", data={"akcja": "propozycje", "numer": NUMER,
                          "folder_zlecenia": FOLDER}, follow_redirects=True)
html = r.get_data(as_text=True)
assert r.status_code == 200
with c.session_transaction() as s:
    assert "propozycje" not in s, "propozycje maja byc w pliku, nie w ciasteczku"
    assert s.get("prop_id")
print("\nstrona po 'Zaproponuj':", r.status_code, "| ciasteczko sesji bez listy wykazow")
assert 'name="wykaz" id="wykaz"' in html, "wykaz ma byc polem tekstowym"
assert "<select" not in html.split("2. Wykaz roboczy")[1].split("3. Pliki DXF")[0]
assert 'name="folder_zlecenia"' in html
wart = html.split('name="folder_zlecenia"')[1].split('value="')[1].split('"')[0]
print("folder zlecenia w polu:", wart)
assert "REWIZJA" in wart
wyk = html.split('id="wykaz"')[1].split('value="')[1].split('"')[0]
print("wykaz w polu          :", wyk)
print("propozycji wykazu     :", html.count('data-wartosc=') )
for linia in html.splitlines():
    if 'class="flash' in linia:
        print("  flash:", linia.strip()[:160])
print("\nOK")
