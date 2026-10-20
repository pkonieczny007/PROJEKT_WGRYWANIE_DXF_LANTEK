# -*- coding: utf-8 -*-
"""Kroki: start -> kontrola -> XML -> wgranie -> kontrola po.

Stan miedzy krokami trzymamy w folderze przebiegu (pliki JSON), a w sesji tylko
sciezke do niego. Dzieki temu nic nie ginie po odswiezeniu strony i kazdy krok
da sie powtorzyc.
"""
from __future__ import annotations

import json
import threading
import traceback
import uuid
from pathlib import Path

from flask import (current_app, flash, jsonify, redirect, render_template, request,
                   send_file, send_from_directory, session, url_for)

from services import (dxf_check, eksport, kontrola, powersync, raport, rejestr_zrodel, ruty,
                      wykaz as W)
from services import lantek_db as db
from services import xml_sheetparts as X
from services import zamowienia as ZAM
from services import zlecenie as Z
from services.marszruta import MASZYNY, NieznanyKod, operacje as operacje_kodu
from services.wspolne import cp1250_ok, do_liczby, sciezka

from . import bp

STAN = "stan.json"
_WGRYWANIE = threading.Lock()      # XmlImporter - tylko jeden import naraz


# --------------------------------------------------------------- pomocnicze

def _folder():
    f = session.get("folder")
    return sciezka(f) if f else None


def _stan(nowy=None):
    f = _folder()
    if f is None:
        return {}
    p = f / STAN
    if nowy is not None:
        stary = _stan()
        stary.update(nowy)
        p.write_text(json.dumps(stary, ensure_ascii=False, indent=2, default=str),
                     encoding="utf-8")
        return stary
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def _prop(nowe=None):
    """Propozycje po numerze zlecenia - w pliku, w sesji tylko identyfikator.
    Lista wykazow i folderow potrafi przekroczyc 4 KB ciasteczka sesji."""
    kat = sciezka(current_app.config["DATA_DIR"]) / "_propozycje"
    if nowe is not None:
        kat.mkdir(parents=True, exist_ok=True)
        pid = uuid.uuid4().hex
        (kat / ("%s.json" % pid)).write_text(json.dumps(nowe, ensure_ascii=False),
                                             encoding="utf-8")
        session["prop_id"] = pid
        return nowe
    pid = session.get("prop_id")
    p = kat / ("%s.json" % pid) if pid else None
    if p and p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return None


def _flash_zamowien(numer, ordref):
    """Po odswiezeniu listy: czy zamowienie sprzedazy juz jest w LANTEKU."""
    inf = ZAM.info(numer)
    if inf["blad"]:
        flash("Nie pobralem zamowien sprzedazy z LANTEKA: %s" % inf["blad"], "warning")
        return
    jest = next((z for z in inf["zamowienia"] if z["ordref"] == ordref), None)
    if jest:
        flash("Zamowienie sprzedazy %s JEST w LANTEKU (%d linii, %s) - nowe linie "
              "dopiszemy od %d." % (ordref, jest["linii"], jest["stan"],
                                    jest["max_linia"] + 1), "info")
    elif inf["zamowienia"]:
        flash("Zamowienia %s nie ma w LANTEKU. Sa inne dla tego zlecenia: %s."
              % (ordref, ", ".join(z["ordref"] for z in inf["zamowienia"])), "warning")
    else:
        flash("W LANTEKU nie ma jeszcze zadnego zamowienia sprzedazy dla %s - "
              "%s zostanie zalozone przy wgraniu." % (numer, ordref), "info")


def _polacz():
    try:
        return db.polacz(current_app.config["DB"])
    except Exception as e:
        flash("Baza LANTEKA niedostepna: %s. Kontrola bedzie niepelna." % e, "warning")
        return None


def _pliki():
    f = _folder()
    if not f or not f.is_dir():
        return []
    return sorted(p.name for p in f.iterdir()
                  if p.suffix.lower() in (".html", ".xml", ".json"))


def _wczytaj_wykaz(st):
    return W.wczytaj(st["wykaz"], kolumna_nazwy=st.get("kolumna_nazwy") or None,
                     kolumna_ilosci=st.get("kolumna_ilosci") or None,
                     zrodlo=st.get("zrodlo_wymiarow", "referencja"))


def _kontroluj(st, cn):
    wyk = _wczytaj_wykaz(st)
    szablony = ruty.wczytaj_z_bazy(cn) if cn else None
    wynik = kontrola.przed(
        wyk, st["foldery_dxf"], st.get("ordref") or "", cn=cn,
        podfoldery=st.get("podfoldery", False), badaj_dxf=st.get("badaj_dxf", True),
        szablony_rut=szablony, tryb_ilosci=st.get("tryb_ilosci", "stop"),
        maszyny_grup=st.get("maszyny_grup") or {}, poprawki=st.get("poprawki") or {})
    return wyk, wynik


# ------------------------------------------------------------------- widoki

@bp.route("/", methods=["GET", "POST"])
def start():
    cfg = current_app.config
    prop = _prop()
    st = _stan()

    if request.method == "POST":
        akcja = request.form.get("akcja")

        if akcja == "nowy":
            session.clear()
            return redirect(url_for("dxf.start"))

        if akcja == "propozycje":
            numer = (request.form.get("numer") or "").strip()
            ZAM.odswiez(cfg["DB"], wymus=True)
            prop = Z.propozycje(numer, cfg["KORZENIE_TECHNOLOGIA"], cfg["KORZENIE_DXF"],
                                cfg["GLEBOKOSC_SKANU"],
                                folder=request.form.get("folder_zlecenia"))
            _prop(prop)
            session["numer"] = numer
            for u in prop["uwagi"]:
                flash(u, "warning")
            if prop["wykazy"]:
                flash("Znalazlem %d wykazow i %d folderow z DXF."
                      % (len(prop["wykazy"]), len(prop["foldery_dxf"])), "info")
            if prop["ordref"]:
                _flash_zamowien(numer, prop["ordref"])
            return redirect(url_for("dxf.start"))

        if akcja == "kontrola":
            numer = (request.form.get("numer") or "").strip()
            wykaz_plik = (request.form.get("wykaz") or "").strip()
            foldery = [f.strip() for f in request.form.getlist("folder_dxf") if f.strip()]
            reczny = (request.form.get("folder_reczny") or "").strip()
            if reczny:
                foldery.insert(0, reczny)
            if not wykaz_plik or not foldery:
                flash("Podaj wykaz i przynajmniej jeden folder z plikami DXF.", "danger")
                return redirect(url_for("dxf.start"))

            folder = Z.folder_przebiegu(cfg["DATA_DIR"], numer)
            session["folder"] = str(folder)
            session["numer"] = numer
            st = _stan({
                "numer": numer, "wykaz": wykaz_plik, "foldery_dxf": foldery,
                "ordref": (request.form.get("ordref") or "").strip(),
                "kolumna_nazwy": (request.form.get("kolumna_nazwy") or "").strip(),
                "kolumna_ilosci": (request.form.get("kolumna_ilosci") or "").strip(),
                "podfoldery": bool(request.form.get("podfoldery")),
                "badaj_dxf": bool(request.form.get("badaj_dxf")),
                "tryb_ilosci": request.form.get("tryb_ilosci", "stop"),
                "zrodlo_wymiarow": request.form.get("zrodlo_wymiarow", "referencja"),
                "dokladaj_spawanie": bool(request.form.get("dokladaj_spawanie")),
                "dokladaj_ocynk": bool(request.form.get("dokladaj_ocynk")),
                "wymus_marszrute": bool(request.form.get("wymus_marszrute")),
            })
            return redirect(url_for("dxf.przebieg"))

    numer = session.get("numer", "")
    if numer:
        ZAM.odswiez(cfg["DB"])
    return render_template("dxf/start.html", prop=prop, numer=numer, st=st,
                           zam=ZAM.info(numer) if numer else None)


@bp.route("/api/zlecenie")
def api_zlecenie():
    """Na biezaco przy wpisywaniu numeru: folder zlecenia + zamowienia sprzedazy.
    Pierwsze wywolanie pobiera swieza liste zamowien z LANTEKA."""
    cfg = current_app.config
    numer = (request.args.get("numer") or "").strip()
    nn, xxxx = Z.rozbierz(numer)
    if not nn:
        return jsonify(ok=False, numer=numer)
    ZAM.odswiez(cfg["DB"], wymus=bool(request.args.get("odswiez")))
    out = Z.podpowiedz_folderu(numer, cfg["KORZENIE_TECHNOLOGIA"])
    out.update(ZAM.info(numer))
    out.update(ok=True, numer=numer, ordref=Z.domyslny_ordref(numer))
    return jsonify(out)


@bp.route("/przebieg", methods=["GET", "POST"])
def przebieg():
    if not _folder():
        flash("Zacznij od wskazania wykazu i folderu z DXF.", "info")
        return redirect(url_for("dxf.start"))
    st = _stan()
    cfg = current_app.config

    if request.method == "POST":
        akcja = request.form.get("akcja")
        try:
            if akcja == "kontrola":
                return _krok_kontrola(st, cfg)
            if akcja == "xml":
                return _krok_xml(st, cfg)
            if akcja == "wgraj":
                return _krok_wgraj(st, cfg)
            if akcja == "zmiany":
                return _krok_zmiany(st, cfg)
            if akcja == "po":
                return _krok_po(st, cfg)
        except Exception as e:
            current_app.logger.error(traceback.format_exc())
            flash("%s: %s" % (type(e).__name__, e), "danger")
        return redirect(url_for("dxf.przebieg"))

    st = _stan()
    return render_template("dxf/przebieg.html", st=st, pliki=_pliki(),
                           folder=str(_folder()), historia=_historia(st, cfg),
                           haslo=_haslo(st), maszyny=MASZYNY)


def _krok_kontrola(st, cfg):
    cn = _polacz()
    wyk, wynik = _kontroluj(st, cn)

    # podpowiedz, gdyby lepsza byla inna kolumna referencji
    mapa = {}
    for f in st["foldery_dxf"]:
        try:
            for k, v in dxf_check.zbierz(f, st.get("podfoldery", False)).items():
                mapa.setdefault(k, []).extend(v)
        except Exception:
            pass
    kand = W.kandydaci_nazwy_wg_dxf(st["wykaz"], {p.stem for v in mapa.values() for p in v})
    if kand and kand[0]["kolumna"] != wyk.kolumna_nazwy and kand[0]["trafien"] > 0:
        flash("Kolumna '%s' trafia w %d plikow DXF, a wybrana '%s' w %d. Mozesz zmienic "
              "kolumne referencji na stronie startowej."
              % (kand[0]["kolumna"], kand[0]["trafien"], wyk.kolumna_nazwy,
                 next((k["trafien"] for k in kand if k["kolumna"] == wyk.kolumna_nazwy), 0)),
              "warning")

    pliki = raport.zapisz_przed(wynik, _folder(), tytul_dodatkowy=Path(st["wykaz"]).name)
    def _opis(w):
        return {
            "ref": w.ref, "material": w.material, "gatunek": w.poz.gatunek,
            "grubosc": w.poz.grubosc, "ilosc": w.poz.ilosc,
            "dxf_zrodlo": str(w.plik_dxf) if w.plik_dxf else None,
            "stan_dxf": w.stan_dxf,
            "kod": w.kod, "ruta": w.ruta, "marszruta": w.marszruta,
            "kod_gnie": w.kod_gnie, "ruta_gnie": w.ruta_gnie, "poziom": w.poziom,
            "wiersz": w.poz.wiersz,
            "grubosc_ref": w.poz.grubosc_ref, "grubosc_kol": w.poz.grubosc_kol,
            "gatunek_ref": w.poz.gatunek_ref, "gatunek_kol": w.poz.gatunek_kol,
            "uwagi": ["%s: %s" % (u.kod, u.opis) for u in w.uwagi],
            "w_zamowieniach": w.w_zamowieniach,
            "ref_dxf": w.poz.ref_dxf or w.ref, "ref_wykaz": w.poz.ref_wykaz,
            "strona": w.poz.strona, "w_bazie": bool(w.w_bazie),
            "maszyna": w.maszyna, "maszyna_lantek": w.maszyna_lantek,
            "maszyna_zrodlo": w.maszyna_zrodlo, "popraw_marszrute": w.popraw_marszrute,
            "klucz_grupy": kontrola.klucz_grupy(w.poz.grubosc, w.poz.gatunek),
            "reczne": w.poz.reczne, "ruta_reczna": w.ruta_reczna,
            "operacje_reczne": w.operacje_reczne,
        }

    do_wgrania = [_opis(w) for w in wynik.do_wgrania]
    podglad = [_opis(w) for w in wynik.wiersze[:5000]]

    _stan({"kontrola": {
        "werdykt": wynik.werdykt, "licznik": wynik.licznik(), "kody": wynik.kody(),
        "raport": pliki["html"], "json": pliki["json"],
        "blacha": wyk.blacha, "kolumna_nazwy": wyk.kolumna_nazwy,
        "kolumna_ilosci": wyk.kolumna_ilosci,
        "zamowienie_istnieje": wynik.zamowienie_istnieje,
        "pierwsza_linia": wynik.pierwsza_linia,
        "baza_dostepna": wynik.baza_dostepna,
        "sierot": len(wynik.sieroty),
        "materialy": wynik.materialy,
        "zrodlo_wymiarow": st.get("zrodlo_wymiarow", "referencja"),
        "wszystkich": len(wynik.wiersze),
        "bilans": wynik.bilans,
        "do_poprawy_maszyny": sum(1 for w in wynik.do_wgrania if w.popraw_marszrute),
        "matrefy": wynik.matrefy, "ruty": wynik.ruty,
        "zmian_recznych": sum(1 for w in wynik.wiersze
                              if w.poz.reczne or w.ruta_reczna or w.maszyna_zrodlo == "pozycja"
                              or w.ref != (w.poz.ref_dxf or w.ref)),
        "bez_giecia_a_powinno": sum(1 for w in wynik.wiersze
                                    if w.kod_gnie and not w.ruta_gnie),
    }, "do_wgrania": do_wgrania, "podglad": podglad,
        "xml": None, "wgranie": None, "po": None})
    flash("Kontrola gotowa: werdykt %s, do wgrania %d z %d pozycji."
          % (wynik.werdykt, len(do_wgrania), len(wynik.wiersze)),
          "success" if wynik.werdykt == kontrola.OK else "warning")

    # plik Excel podgladu odswiezany przy kazdej kontroli (takze po 'Zastosuj zmiany')
    st_nowy = _stan()
    try:
        eksport.zbuduj(st_nowy).save(str(_folder() / eksport.nazwa_pliku(st_nowy)))
    except PermissionError:
        flash("Nie odswiezylem %s - plik jest otwarty w Excelu. Zamknij go albo uzyj "
              "przycisku 'Eksport Excel'." % eksport.nazwa_pliku(st_nowy), "warning")
    return redirect(url_for("dxf.przebieg"))


@bp.route("/eksport")
def eksport_xlsx():
    """Excel z podgladu (Pozycje + Materialy) - zawsze swiezy, ze stanu po kontroli."""
    if not _folder():
        return redirect(url_for("dxf.start"))
    st = _stan()
    if not st.get("kontrola"):
        flash("Najpierw uruchom kontrole.", "warning")
        return redirect(url_for("dxf.przebieg"))
    return send_file(eksport.do_pamieci(st), as_attachment=True,
                     download_name=eksport.nazwa_pliku(st),
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _krok_zmiany(st, cfg):
    """Zmiany czlowieka z podgladu: maszyna dla grupy grubosc+gatunek, a dla
    pojedynczej pozycji: referencja, maszyna, material i ruta (tylko z listy
    INTEGRY), grubosc i ilosc. Domyslnie nic - to tylko alternatywa. Formularz
    przysyla PELNY stan (JSON), wiec zastepujemy poprzedni i powtarzamy kontrole."""
    try:
        zm = json.loads(request.form.get("zmiany_json") or "{}")
    except ValueError:
        flash("Nie udalo sie odczytac zmian - sprobuj jeszcze raz.", "danger")
        return redirect(url_for("dxf.przebieg"))
    dozwolone = set(MASZYNY)
    k = st.get("kontrola") or {}
    matrefy = set(k.get("matrefy") or [])
    ruty_ok = {r["ref"] for r in k.get("ruty") or []}
    grupy = {kl: v for kl, v in (zm.get("grupy") or {}).items() if v in dozwolone}
    poprawki, odrzucone = {}, []
    for ref_dxf, z in (zm.get("pozycje") or {}).items():
        wpis = {}
        if (z.get("ref") or "").strip() and z["ref"].strip() != ref_dxf:
            wpis["ref"] = z["ref"].strip()
        if z.get("maszyna") in dozwolone:
            wpis["maszyna"] = z["maszyna"]
        if z.get("material"):
            if z["material"] in matrefy:
                wpis["material"] = z["material"]
            else:
                odrzucone.append("%s: material '%s' spoza INTEGRY" % (ref_dxf, z["material"]))
        if z.get("ruta"):
            if z["ruta"] in ruty_ok:
                wpis["ruta"] = z["ruta"]
            else:
                odrzucone.append("%s: ruta '%s' spoza INTEGRY" % (ref_dxf, z["ruta"]))
        for pole in ("grubosc", "ilosc"):
            if z.get(pole) not in (None, ""):
                v = do_liczby(z[pole])
                if v and v > 0:
                    wpis[pole] = v
                else:
                    odrzucone.append("%s: %s '%s' to nie liczba > 0" % (ref_dxf, pole, z[pole]))
        if wpis:
            poprawki[ref_dxf] = wpis
    for o in odrzucone[:5]:
        flash("Pominiete: " + o, "warning")
    _stan({"maszyny_grup": grupy, "poprawki": poprawki})
    flash("Zapisane: maszyna dla %d grup, wyjatki dla %d pozycji. Kontrola powtorzona."
          % (len(grupy), len(poprawki)), "info")
    return _krok_kontrola(_stan(), cfg)


@bp.route("/api/ref")
def api_ref():
    """Przy edycji referencji: czy taka juz jest w LANTEKU (kartoteka, zamowienia)."""
    ref = (request.args.get("ref") or "").strip()
    out = {"ref": ref, "dlugosc": len(ref), "za_dluga": len(ref) > 40,
           "znaki": cp1250_ok(ref), "w_bazie": None, "w_zamowieniach": []}
    if not ref:
        return jsonify(out)
    try:
        cn = db.polacz(current_app.config["DB"])
    except Exception as e:
        out["blad"] = str(e)
        return jsonify(out)
    try:
        d = db.produkty_po_ref(cn, [ref]).get(ref)
        out["w_bazie"] = bool(d)
        if d:
            out["material"] = (d.get("DIS_MatRef") or "").strip()
            out["grubosc"] = d.get("DIS_Thickness")
            out["zalozony"] = str(d.get("CrtDate"))[:16]
        out["w_zamowieniach"] = db.zamowienia_po_ref(cn, [ref]).get(ref, [])
    finally:
        cn.close()
    return jsonify(out)


def _krok_xml(st, cfg):
    poz = st.get("do_wgrania") or []
    if not poz:
        if st.get("kontrola"):
            flash("Zadna pozycja nie przeszla kontroli (wszystkie maja STOP) - "
                  "nie ma czego wgrac.", "danger")
        else:
            flash("Najpierw uruchom kontrole.", "danger")
        return redirect(url_for("dxf.przebieg"))
    # elementy juz bedace liniami zamowien: domyslnie BEZ linii (aktualizacja
    # elementu); linie, czyli podwojenie ilosci, tylko gdy czlowiek to zaznaczy
    podwojenie = bool(request.form.get("podwojenie"))

    numer = (st.get("numer") or "bez_numeru").replace(" ", "_")
    kat_dxf = sciezka(cfg["LANTEK_DXF_DIR"])
    if cfg.get("DXF_PODFOLDER", True):
        kat_dxf = kat_dxf / numer
    skopiowane = powersync.kopiuj_dxf(
        [(p["ref"], p["dxf_zrodlo"]) for p in poz if p["dxf_zrodlo"]], kat_dxf)

    elementy = []
    for p in poz:
        elementy.append(X.ElementXML(
            ref=p["ref"], material=p["material"], grubosc=p["grubosc"],
            ilosc=p["ilosc"] or 0, dxf=skopiowane.get(p["ref"]),
            bez_linii=bool(p.get("w_zamowieniach")) and not podwojenie))

    ordref = st.get("ordref") or ""
    xml = X.zapisz(elementy, _folder() / ("SheetParts_%s.xml" % numer),
                   ordref=ordref or None, zaloz_zamowienie=bool(ordref),
                   pierwsza_linia=(st.get("kontrola") or {}).get("pierwsza_linia", 1))
    pods = X.podsumowanie(elementy, ordref, bool(ordref))

    powtorki = [p for p in poz if p.get("w_zamowieniach")]
    dane = {"xml": str(xml), "skopiowanych_dxf": len(skopiowane),
            "katalog_dxf": str(kat_dxf), "podsumowanie": pods,
            "powtorek": len(powtorki),
            "zamowienia_powtorek": sorted({o for p in powtorki for o in p["w_zamowieniach"]}),
            "podwojenie": bool(ordref) and podwojenie and bool(powtorki),
            "podwojonych": len(powtorki) if (ordref and podwojenie) else 0,
            "refy_z_linia": [e.ref for e in elementy if not e.bez_linii] if ordref else [],
            "bez_linii_refy": [e.ref for e in elementy if e.bez_linii] if ordref else []}

    # drugi plik: poprawka marszruty, wgrywana zaraz po imporcie glownym.
    # Zawsze dla pozycji, ktorym regula LANTEKA da inna maszyne niz wybrana;
    # opcjonalnie (checkbox) dla tych, ktorym nie da gietarki.
    pary, bez_kodu = [], []
    for p in poz:
        gietarka = st.get("wymus_marszrute") and p["kod_gnie"] and not p["ruta_gnie"]
        if not (p.get("popraw_marszrute") or gietarka):
            continue
        maszyna = p.get("maszyna") or "laser"
        try:
            if p.get("operacje_reczne"):          # ruta wybrana recznie z INTEGRY
                ops = [tuple(o) for o in p["operacje_reczne"]]
            else:
                ops = operacje_kodu(p["kod"], st.get("dokladaj_spawanie"),
                                    st.get("dokladaj_ocynk"), maszyna=maszyna)
        except NieznanyKod:
            ops = operacje_kodu("", maszyna=maszyna)      # samo wypalanie
            bez_kodu.append(p["ref"])
        pary.append((p["ref"], ops))
    if pary:
        p2 = X.zapisz_marszrute(pary, _folder() / ("Marszruta_%s.xml" % numer))
        dane["xml_marszruta"] = str(p2)
        dane["marszrut_do_poprawy"] = len(pary)
        dane["marszrut_maszyna"] = sum(1 for p in poz if p.get("popraw_marszrute"))
    if bez_kodu:
        flash("%d pozycji z nieznanym kodem technologii dostanie w poprawce samo "
              "wypalanie (np. %s)." % (len(bez_kodu), ", ".join(bez_kodu[:3])), "warning")

    _stan({"xml": dane})
    flash("XML gotowy: %d elementow, %d plikow DXF skopiowanych do %s."
          % (pods["elementow"], len(skopiowane), kat_dxf), "success")
    if dane["podwojenie"]:
        flash("UWAGA: %d elementow, ktore juz sa w zamowieniach (%s), dostanie NOWE "
              "linie zamowienia - ilosci sie podwoja. Przy wgraniu trzeba to potwierdzic."
              % (dane["podwojonych"], ", ".join(dane["zamowienia_powtorek"])), "warning")
    elif pods.get("bez_linii"):
        flash("%d elementow juz jest w zamowieniach (%s) - wejda bez linii zamowienia, "
              "jako aktualizacja elementu." % (pods["bez_linii"],
                                               ", ".join(dane["zamowienia_powtorek"])), "info")
    return redirect(url_for("dxf.przebieg"))


def _historia(st, cfg) -> list:
    """Wczesniejsze wgrania tych samych elementow - z rejestru wgran."""
    refy = [p["ref"] for p in st.get("do_wgrania") or []]
    if not refy and not st.get("numer"):
        return []
    return Z.historia_wgran(cfg["REJESTR"], st.get("numer"), refy)


def _haslo(st) -> str:
    """Co trzeba przepisac, zeby swiadomie wgrac ponownie."""
    x = st.get("xml") or {}
    if x.get("podwojenie") and x.get("podwojonych"):
        return "PODWAJAM"
    return st.get("ordref") or "PONOWNIE"


def _krok_wgraj(st, cfg):
    dane = st.get("xml") or {}
    if not dane.get("xml"):
        flash("Najpierw wygeneruj XML.", "danger")
        return redirect(url_for("dxf.przebieg"))
    if not request.form.get("potwierdzam"):
        flash("Zaznacz potwierdzenie - to jedyny krok, ktory pisze do bazy LANTEKA.",
              "danger")
        return redirect(url_for("dxf.przebieg"))

    # jedno wgrywanie naraz: podwojne klikniecie albo druga karta nie przejda
    # bramki rownolegle, zanim pierwsze cokolwiek zapisze
    if not _WGRYWANIE.acquire(blocking=False):
        flash("PRZERWANE: wgrywanie juz trwa (drugie klikniecie albo inna karta). "
              "Poczekaj na wynik pierwszego.", "danger")
        return redirect(url_for("dxf.przebieg"))
    try:
        return _wgraj_po_bramce(st, cfg, dane)
    finally:
        _WGRYWANIE.release()


def _przerwij(tekst):
    flash("PRZERWANE: " + tekst, "danger")
    return redirect(url_for("dxf.przebieg"))


def _wgraj_po_bramce(st, cfg, dane):
    refy = [p["ref"] for p in st.get("do_wgrania", [])]

    # bramka 1: swieze pytanie do bazy tuz przed zapisem - czy elementy, ktorym
    # XML dopisuje linie, nie weszly do zamowienia juz PO zbudowaniu XML
    cn = _polacz()
    powtorki = db.zamowienia_po_ref(cn, refy) if cn is not None else {}
    if not dane.get("podwojenie"):
        swieze = sorted(r for r in dane.get("refy_z_linia") or [] if r in powtorki)
        if swieze:
            return _przerwij(
                "%d elementow, ktorym XML dopisuje linie zamowienia, jest juz w zamowieniu "
                "(np. %s) - wgrane po zbudowaniu XML. Powtorz kontrole i zbuduj XML ponownie."
                % (len(swieze), ", ".join(swieze[:3])))

    # bramka 2: ponowne wgranie (baza albo rejestr) albo podwojenie -> swiadoma zgoda
    historia = Z.historia_wgran(cfg["REJESTR"], st.get("numer"), refy)
    podwaja = bool(dane.get("podwojenie") and dane.get("podwojonych"))
    ponowne = bool(powtorki) or bool(historia)
    if ponowne or podwaja:
        haslo = _haslo(st)
        wpisane = (request.form.get("haslo") or "").strip()
        if not request.form.get("ponownie") or wpisane.upper() != haslo.upper():
            powod = []
            if powtorki:
                powod.append("%d elementow jest juz w zamowieniach" % len(powtorki))
            if historia:
                powod.append("ostatnie wgranie %s" % historia[0].get("czas", "?").replace("T", " "))
            return _przerwij(
                "to jest PONOWNE wgranie (%s). Zaznacz 'wgrywam ponownie swiadomie' "
                "i wpisz %s." % ("; ".join(powod) or "podwojenie linii", haslo))

    wynik = powersync.wgraj(dane["xml"], cfg["XMLIMPORTER_EXE"], cfg["IMPORTER_LOG_DIR"],
                            _folder(), user=cfg["XMLIMPORTER_USER"],
                            haslo=cfg["XMLIMPORTER_PASS"])
    html = raport.zapisz_wgranie(wynik, _folder(), dane["xml"],
                                 len(st.get("do_wgrania", [])))
    wgranie = {"podsumowanie": wynik.podsumowanie(), "bledow": wynik.bledow,
               "log": wynik.log, "raport": html, "udany": wynik.udany,
               "ponowne": ponowne, "podwojenie": podwaja}

    # poprawka marszruty (maszyna / gietarka) - zawsze PO imporcie glownym, bo
    # IMPORTGEO przebudowuje marszrute; tylko gdy glowny przeszedl bez bledow
    if dane.get("xml_marszruta"):
        if wynik.udany:
            w2 = powersync.wgraj(dane["xml_marszruta"], cfg["XMLIMPORTER_EXE"],
                                 cfg["IMPORTER_LOG_DIR"], _folder(),
                                 user=cfg["XMLIMPORTER_USER"], haslo=cfg["XMLIMPORTER_PASS"])
            raport.zapisz_wgranie(w2, _folder(), dane["xml_marszruta"],
                                  dane.get("marszrut_do_poprawy", 0))
            wgranie["marszruta"] = {"podsumowanie": w2.podsumowanie(), "udany": w2.udany,
                                    "bledow": w2.bledow, "log": w2.log,
                                    "pozycji": dane.get("marszrut_do_poprawy", 0)}
            flash("Poprawka marszruty (%d pozycji): %s"
                  % (dane.get("marszrut_do_poprawy", 0), w2.podsumowanie()),
                  "success" if w2.udany else "danger")
        else:
            wgranie["marszruta"] = {"podsumowanie": "nie wgrana - import glowny mial bledy",
                                    "udany": False, "pozycji": dane.get("marszrut_do_poprawy", 0)}
            flash("Poprawki marszruty NIE wgrano, bo import glowny mial bledy.", "danger")
    _stan({"wgranie": wgranie})

    # wspolny rejestr zrodel (Excel na QNAP): skad wzielismy DXF do tego wgrania
    if wynik.uruchomiony:
        uwagi = []
        if ponowne:
            uwagi.append("ponowne wgranie")
        if podwaja:
            uwagi.append("PODWOJENIE linii zamowienia")
        if wgranie.get("marszruta"):
            uwagi.append("poprawka marszruty %s poz.: %s" % (
                wgranie["marszruta"].get("pozycji"), wgranie["marszruta"].get("podsumowanie")))
        recznych = (st.get("kontrola") or {}).get("zmian_recznych")
        if recznych:
            uwagi.append("zmian recznych przy pozycjach: %s" % recznych)
        wiersze = rejestr_zrodel.wiersze_wgrania(
            dict(st, folder_przebiegu=str(_folder())), wynik.podsumowanie(), "; ".join(uwagi))
        rz = rejestr_zrodel.dopisz(cfg["REJESTR_ZRODEL_DIR"], wiersze)
        wgranie["rejestr_zrodel"] = rz
        _stan({"wgranie": wgranie})
        if rz["ok"]:
            flash("Rejestr zrodel DXF: dopisano %d folderow (%s)." % (len(wiersze), rz["plik"]),
                  "info")
        else:
            flash("Rejestr zrodel DXF NIE zapisany: %s. %s" % (
                rz["blad"], "Wiersze czekaja w kolejce i dopisza sie przy nastepnym wgraniu."
                if rz["oczekuje"] else ""), "warning")

    Z.zapisz_rejestr(cfg["REJESTR"], {
        "zlecenie": st.get("numer"), "ordref": st.get("ordref"),
        "elementow": len(refy), "xml": dane["xml"],
        "bledow": wynik.bledow, "udany": wynik.udany, "folder": str(_folder()),
        "ponowne": ponowne, "podwojenie": podwaja,
        "linii_zamowienia": dane.get("podsumowanie", {}).get("linii_zamowienia"),
        "refy": refy})
    flash("Wgranie: %s" % wynik.podsumowanie(),
          "success" if wynik.udany else "danger")
    return redirect(url_for("dxf.przebieg"))


def _krok_po(st, cfg):
    cn = _polacz()
    if cn is None:
        flash("Kontrola po wgraniu wymaga bazy LANTEKA.", "danger")
        return redirect(url_for("dxf.przebieg"))
    wyk, wynik = _kontroluj(st, cn)
    wgrane_refy = {p["ref"] for p in st.get("do_wgrania", [])}
    wiersze = [w for w in wynik.wiersze if w.ref in wgrane_refy]
    wynik_po = kontrola.po(cn, wiersze, st.get("ordref") or "",
                           bez_linii=(st.get("xml") or {}).get("bez_linii_refy") or ())
    pliki = raport.zapisz_po(wynik_po, _folder())
    z_gieciem = sum(1 for w in wynik_po.wiersze if w["ma_giecie"])
    _stan({"po": {"werdykt": wynik_po.werdykt, "raport": pliki["html"],
                  "sprawdzonych": len(wynik_po.wiersze), "z_gieciem": z_gieciem}})
    flash("Kontrola po wgraniu: %s (%d z %d ma gietarke w marszrucie)."
          % (wynik_po.werdykt, z_gieciem, len(wynik_po.wiersze)),
          "success" if wynik_po.werdykt == kontrola.OK else "warning")
    return redirect(url_for("dxf.przebieg"))


@bp.route("/pobierz/<path:plik>")
def pobierz(plik):
    f = _folder()
    if not f:
        return redirect(url_for("dxf.start"))
    return send_from_directory(str(f), plik, as_attachment=True)
