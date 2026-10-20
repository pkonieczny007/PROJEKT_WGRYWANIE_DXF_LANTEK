# -*- coding: utf-8 -*-
"""Kroki: start -> kontrola -> XML -> wgranie -> kontrola po.

Stan miedzy krokami trzymamy w folderze przebiegu (pliki JSON), a w sesji tylko
sciezke do niego. Dzieki temu nic nie ginie po odswiezeniu strony i kazdy krok
da sie powtorzyc.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from flask import (current_app, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)

from services import dxf_check, kontrola, powersync, raport, ruty, wykaz as W
from services import lantek_db as db
from services import xml_sheetparts as X
from services import zlecenie as Z
from services.marszruta import operacje as operacje_kodu
from services.wspolne import sciezka

from . import bp

STAN = "stan.json"


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
        szablony_rut=szablony, tryb_ilosci=st.get("tryb_ilosci", "pierwszy"))
    return wyk, wynik


# ------------------------------------------------------------------- widoki

@bp.route("/", methods=["GET", "POST"])
def start():
    cfg = current_app.config
    prop = session.get("propozycje")
    st = _stan()

    if request.method == "POST":
        akcja = request.form.get("akcja")

        if akcja == "nowy":
            session.clear()
            return redirect(url_for("dxf.start"))

        if akcja == "propozycje":
            numer = (request.form.get("numer") or "").strip()
            prop = Z.propozycje(numer, cfg["KORZENIE_TECHNOLOGIA"], cfg["KORZENIE_DXF"],
                                cfg["GLEBOKOSC_SKANU"])
            session["propozycje"] = prop
            session["numer"] = numer
            for u in prop["uwagi"]:
                flash(u, "warning")
            if prop["wykazy"]:
                flash("Znalazlem %d wykazow i %d folderow z DXF."
                      % (len(prop["wykazy"]), len(prop["foldery_dxf"])), "info")
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
                "tryb_ilosci": request.form.get("tryb_ilosci", "pierwszy"),
                "zrodlo_wymiarow": request.form.get("zrodlo_wymiarow", "referencja"),
                "dokladaj_spawanie": bool(request.form.get("dokladaj_spawanie")),
                "dokladaj_ocynk": bool(request.form.get("dokladaj_ocynk")),
                "wymus_marszrute": bool(request.form.get("wymus_marszrute")),
            })
            return redirect(url_for("dxf.przebieg"))

    return render_template("dxf/start.html", prop=prop,
                           numer=session.get("numer", ""), st=st)


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
            if akcja == "po":
                return _krok_po(st, cfg)
        except Exception as e:
            current_app.logger.error(traceback.format_exc())
            flash("%s: %s" % (type(e).__name__, e), "danger")
        return redirect(url_for("dxf.przebieg"))

    return render_template("dxf/przebieg.html", st=_stan(), pliki=_pliki(),
                           folder=str(_folder()))


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
        }

    do_wgrania = [_opis(w) for w in wynik.do_wgrania]
    podglad = [_opis(w) for w in wynik.wiersze[:600]]

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
        "bez_giecia_a_powinno": sum(1 for w in wynik.wiersze
                                    if w.kod_gnie and not w.ruta_gnie),
    }, "do_wgrania": do_wgrania, "podglad": podglad,
        "xml": None, "wgranie": None, "po": None})
    flash("Kontrola gotowa: werdykt %s, do wgrania %d z %d pozycji."
          % (wynik.werdykt, len(do_wgrania), len(wynik.wiersze)),
          "success" if wynik.werdykt == kontrola.OK else "warning")
    return redirect(url_for("dxf.przebieg"))


def _krok_xml(st, cfg):
    poz = st.get("do_wgrania") or []
    if not poz:
        flash("Najpierw uruchom kontrole.", "danger")
        return redirect(url_for("dxf.przebieg"))

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
            ilosc=p["ilosc"] or 0, dxf=skopiowane.get(p["ref"])))

    ordref = st.get("ordref") or ""
    xml = X.zapisz(elementy, _folder() / ("SheetParts_%s.xml" % numer),
                   ordref=ordref or None, zaloz_zamowienie=bool(ordref),
                   pierwsza_linia=(st.get("kontrola") or {}).get("pierwsza_linia", 1))
    pods = X.podsumowanie(elementy, ordref, bool(ordref))

    dane = {"xml": str(xml), "skopiowanych_dxf": len(skopiowane),
            "katalog_dxf": str(kat_dxf), "podsumowanie": pods}

    # opcjonalny drugi plik: wymuszenie marszruty dla pozycji, ktorym regula
    # LANTEKA nie nada gietarki
    if st.get("wymus_marszrute"):
        pary = [(p["ref"], operacje_kodu(p["kod"], st.get("dokladaj_spawanie"),
                                         st.get("dokladaj_ocynk")))
                for p in poz if p["kod_gnie"] and not p["ruta_gnie"]]
        if pary:
            p2 = X.zapisz_marszrute(pary, _folder() / ("Marszruta_%s.xml" % numer))
            dane["xml_marszruta"] = str(p2)
            dane["marszrut_do_poprawy"] = len(pary)

    _stan({"xml": dane})
    flash("XML gotowy: %d elementow, %d plikow DXF skopiowanych do %s."
          % (pods["elementow"], len(skopiowane), kat_dxf), "success")
    return redirect(url_for("dxf.przebieg"))


def _krok_wgraj(st, cfg):
    dane = st.get("xml") or {}
    if not dane.get("xml"):
        flash("Najpierw wygeneruj XML.", "danger")
        return redirect(url_for("dxf.przebieg"))
    if not request.form.get("potwierdzam"):
        flash("Zaznacz potwierdzenie - to jedyny krok, ktory pisze do bazy LANTEKA.",
              "danger")
        return redirect(url_for("dxf.przebieg"))

    # bramka: swieze pytanie do bazy tuz przed zapisem
    cn = _polacz()
    if cn is not None:
        refy = [p["ref"] for p in st.get("do_wgrania", [])]
        ordref = st.get("ordref") or ""
        if ordref:
            juz = {(r.get("PrdRef") or "").strip() for r in db.linie_zamowienia(cn, ordref)}
            kolizje = sorted(set(refy) & juz)
            if kolizje:
                flash("PRZERWANE: %d elementow jest juz linia zamowienia '%s' "
                      "(np. %s). Ponowne wgranie zdublowaloby pozycje."
                      % (len(kolizje), ordref, ", ".join(kolizje[:3])), "danger")
                return redirect(url_for("dxf.przebieg"))

    wynik = powersync.wgraj(dane["xml"], cfg["XMLIMPORTER_EXE"], cfg["IMPORTER_LOG_DIR"],
                            _folder(), user=cfg["XMLIMPORTER_USER"],
                            haslo=cfg["XMLIMPORTER_PASS"], limit_s=cfg["IMPORT_TIMEOUT_S"])
    html = raport.zapisz_wgranie(wynik, _folder(), dane["xml"],
                                 len(st.get("do_wgrania", [])))
    _stan({"wgranie": {"podsumowanie": wynik.podsumowanie(), "bledow": wynik.bledow,
                       "log": wynik.log, "raport": html, "udany": wynik.udany}})
    Z.zapisz_rejestr(cfg["REJESTR"], {
        "zlecenie": st.get("numer"), "ordref": st.get("ordref"),
        "elementow": len(st.get("do_wgrania", [])), "xml": dane["xml"],
        "bledow": wynik.bledow, "folder": str(_folder())})
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
    wynik_po = kontrola.po(cn, wiersze, st.get("ordref") or "")
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
