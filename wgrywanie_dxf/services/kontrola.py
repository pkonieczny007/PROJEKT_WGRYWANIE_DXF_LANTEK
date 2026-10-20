# -*- coding: utf-8 -*-
"""Kontrola PRZED wgraniem i PO wgraniu.

Poziomy: OK / UWAGA (mozna wgrac po potwierdzeniu) / STOP (blokada).
Zadna regula nie zmienia danych - kontrola tylko czyta i melduje.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import dxf_check, marszruta, ruty
from .wspolne import MAX_REF, cp1250_ok, do_liczby, liczba_txt

MAPOWANIE = json.loads((Path(__file__).resolve().parent.parent / "mapowanie.json")
                       .read_text(encoding="utf-8"))
MATERIALY = {k.replace(" ", "").upper(): v for k, v in MAPOWANIE["materialy"].items()}

STOP, UWAGA, OK = "STOP", "UWAGA", "OK"
WAGA = {OK: 0, UWAGA: 1, STOP: 2}


@dataclass
class Uwaga:
    poziom: str
    kod: str
    opis: str
    ref: str = ""
    wiersz: int | None = None


@dataclass
class Wiersz:
    """Jedna pozycja wykazu przygotowana do wgrania + jej werdykt.

    Gdy ta sama referencja stoi w kilku wierszach wykazu (ta sama czesc wymieniona
    przy kilku zlozeniach), scalamy ja w JEDNA pozycje - do LANTEKA i tak idzie
    jeden produkt. 'wiersze_zrodlowe' pamieta, skad sie wziela.
    """
    poz: object                       # services.wykaz.Pozycja
    wiersze_zrodlowe: list = field(default_factory=list)
    ilosc_suma: float | None = None   # suma ilosci ze wszystkich wierszy
    material: str = ""
    plik_dxf: object = None
    stan_dxf: str = ""
    dxf_info: object = None
    kod: str = ""
    ruta: str = ""                    # przewidziana ruta LANTEKA
    marszruta: str = ""               # operacje tej ruty
    ruta_gnie: bool = False
    kod_gnie: bool = False
    w_bazie: dict | None = None
    marszruta_w_bazie: str = ""
    uwagi: list = field(default_factory=list)

    @property
    def ref(self):
        return self.poz.ref

    @property
    def poziom(self):
        return max([u.poziom for u in self.uwagi], key=lambda p: WAGA[p]) if self.uwagi else OK

    def dodaj(self, poziom, kod, opis):
        self.uwagi.append(Uwaga(poziom, kod, opis, self.ref, self.poz.wiersz))


@dataclass
class Wynik:
    wiersze: list = field(default_factory=list)
    ogolne: list = field(default_factory=list)      # Uwaga bez konkretnej pozycji
    sieroty: list = field(default_factory=list)
    materialy: list = field(default_factory=list)   # gatunek -> MatRef, ile pozycji
    baza_dostepna: bool = False
    ordref: str = ""
    zamowienie_istnieje: bool = False
    pierwsza_linia: int = 1

    @property
    def werdykt(self):
        poziomy = [w.poziom for w in self.wiersze] + [u.poziom for u in self.ogolne]
        return max(poziomy, key=lambda p: WAGA[p]) if poziomy else OK

    @property
    def do_wgrania(self):
        return [w for w in self.wiersze if w.poziom != STOP]

    def licznik(self):
        c = {OK: 0, UWAGA: 0, STOP: 0}
        for w in self.wiersze:
            c[w.poziom] += 1
        return c

    def kody(self):
        c = {}
        for w in self.wiersze:
            for u in w.uwagi:
                c[u.kod] = c.get(u.kod, 0) + 1
        for u in self.ogolne:
            c[u.kod] = c.get(u.kod, 0) + 1
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def material_lantek(gatunek) -> str | None:
    """Gatunek z referencji -> MatRef istniejacy w kartotece LANTEKA."""
    if not gatunek:
        return None
    return MATERIALY.get(str(gatunek).replace(" ", "").upper())


def podpowiedz_material(gatunek, materialy_bazy) -> list:
    """Najblizsze istniejace MatRef - zeby czlowiek wiedzial, co dopisac do mapowania."""
    if not gatunek or not materialy_bazy:
        return []
    g = str(gatunek).replace(" ", "").upper()
    zawiera = [m for m in materialy_bazy if g in m.replace(" ", "").upper()
               or m.replace(" ", "").upper() in g]
    if zawiera:
        return sorted(zawiera)[:6]
    import difflib
    return difflib.get_close_matches(g, sorted(materialy_bazy), n=5, cutoff=0.5)


def zestawienie_materialow(wiersze, materialy_bazy=None) -> list:
    """Co na co idzie - do pokazania czlowiekowi PRZED wgraniem.
    Grupa = grubosc + gatunek (-> MatRef); liczymy pozycje i sztuki (ilosc, ktora
    idzie do XML jako Quantity). Sortowanie: MatRef, potem grubosc rosnaco."""
    licz = {}
    for w in wiersze:
        gat = (w.poz.gatunek or "(brak)")
        klucz = (do_liczby(w.poz.grubosc), gat, w.material or "(brak mapowania)")
        g = licz.setdefault(klucz, {"pozycji": 0, "sztuk": 0.0})
        g["pozycji"] += 1
        g["sztuk"] += do_liczby(w.poz.ilosc) or 0
    out = []
    for (grub, gat, mat), g in sorted(
            licz.items(), key=lambda kv: (kv[0][2], kv[0][0] is None, kv[0][0] or 0)):
        out.append({
            "grubosc": liczba_txt(grub) or "(brak)", "gatunek": gat, "material": mat,
            "pozycji": g["pozycji"], "sztuk": float(liczba_txt(g["sztuk"]) or 0),
            "w_kartotece": (None if not materialy_bazy else mat in materialy_bazy),
        })
    return out


def suma_materialow(materialy) -> dict:
    """Wiersz SUMA pod zestawieniem materialow."""
    return {"grup": len(materialy),
            "pozycji": sum(m.get("pozycji", 0) for m in materialy),
            "sztuk": sum(m.get("sztuk", 0) or 0 for m in materialy)}


def _scal_duplikaty(pozycje, tryb_ilosci="pierwszy"):
    """Ta sama referencja w kilku wierszach -> jedna pozycja.

    tryb_ilosci:
      'pierwszy' - ilosc z pierwszego wiersza (zgodna z czlonem 'Nst' referencji),
      'suma'     - suma ilosci ze wszystkich wierszy.
    Zwraca [(pozycja, wiersze_zrodlowe, ilosc_suma, rozbieznosci)].
    """
    grupy = {}
    kolejnosc = []
    for p in pozycje:
        klucz = p.ref or ("__pusta__%d" % p.wiersz)
        if klucz not in grupy:
            grupy[klucz] = []
            kolejnosc.append(klucz)
        grupy[klucz].append(p)

    out = []
    for klucz in kolejnosc:
        lista = grupy[klucz]
        pierwsza = lista[0]
        suma = sum(x.ilosc or 0 for x in lista)
        rozbieznosci = []
        if len(lista) > 1:
            for nazwa, pole in (("grubosc", "grubosc"), ("gatunek", "gatunek"),
                                ("kod technologii", "kod")):
                wartosci = {getattr(x, pole) for x in lista}
                if len(wartosci) > 1:
                    rozbieznosci.append("%s: %s" % (nazwa, sorted(map(str, wartosci))))
            if tryb_ilosci == "suma":
                pierwsza.ilosc = suma
        out.append((pierwsza, [x.wiersz for x in lista], suma, rozbieznosci))
    return out


def przed(wykaz, folder_dxf, ordref, cn=None, podfoldery=False, badaj_dxf=True,
          szablony_rut=None, dokladaj_spawanie=False, dokladaj_ocynk=False,
          jawne_operacje=False, tryb_ilosci="pierwszy") -> Wynik:
    """Pelna kontrola przed wgraniem. cn=None -> bez czesci bazodanowej.

    folder_dxf moze byc pojedyncza sciezka albo lista sciezek (czesc zlecen ma
    DXF-y w kilku folderach: z bazy, z bazy P+L, rysowane).
    """
    wynik = Wynik(ordref=ordref)

    if wykaz.formuly_puste:
        wynik.ogolne.append(Uwaga(STOP, "FORMULA_NIEPRZELICZONA",
            "%d pozycji ma pusta referencje, bo formula nie zostala przeliczona. "
            "Otworz wykaz w Excelu i zapisz." % wykaz.formuly_puste))
    if ordref and len(ordref) > MAX_REF:
        wynik.ogolne.append(Uwaga(STOP, "ORDREF_ZA_DLUGI",
            "numer zamowienia ma %d znakow, limit LANTEKA to %d" % (len(ordref), MAX_REF)))

    # --- scalenie duplikatow referencji (ta sama czesc w kilku wierszach wykazu)
    scalone = _scal_duplikaty(wykaz.pozycje, tryb_ilosci)
    ile_scalonych = sum(1 for _p, w, _s, _r in scalone if len(w) > 1)
    if ile_scalonych:
        wynik.ogolne.append(Uwaga(UWAGA, "SCALONE_DUPLIKATY",
            "%d referencji wystepuje w wykazie wiecej niz raz - scalone do jednej "
            "pozycji (ilosc: %s)" % (ile_scalonych,
            "suma wierszy" if tryb_ilosci == "suma" else "z pierwszego wiersza")))

    # --- pliki DXF (jeden folder albo kilka)
    foldery = folder_dxf if isinstance(folder_dxf, (list, tuple)) else [folder_dxf]
    foldery = [f for f in foldery if f]
    mapa = {}
    for f in foldery:
        try:
            czastkowa = dxf_check.zbierz(f, podfoldery=podfoldery)
        except Exception as e:
            wynik.ogolne.append(Uwaga(STOP, "FOLDER_DXF", str(e)))
            continue
        for k, v in czastkowa.items():
            mapa.setdefault(k, []).extend(v)
    refy_wykazu = [p.ref for p, _w, _s, _r in scalone]
    dopasowanie = dxf_check.dopasuj(refy_wykazu, mapa)
    wynik.sieroty = dxf_check.sieroty(mapa, refy_wykazu)
    if wynik.sieroty:
        wynik.ogolne.append(Uwaga(UWAGA, "PLIKI_SPOZA_WYKAZU",
            "%d plikow DXF w folderze nie ma odpowiednika w wykazie - nie beda wgrane"
            % len(wynik.sieroty)))

    # --- baza
    produkty, operacje_bazy, materialy_bazy, linie_zam = {}, {}, set(), []
    if cn is not None:
        from . import lantek_db as db
        wynik.baza_dostepna = True
        refy = [r for r in refy_wykazu if r]
        produkty = db.produkty_po_ref(cn, refy)
        operacje_bazy = db.operacje_po_ref(cn, refy)
        materialy_bazy = db.materialy(cn)
        if szablony_rut is None:
            szablony_rut = ruty.wczytaj_z_bazy(cn)
        if ordref:
            wynik.zamowienie_istnieje = bool(db.zamowienie(cn, ordref))
            linie_zam = db.linie_zamowienia(cn, ordref)
            wynik.pierwsza_linia = db.max_linia(cn, ordref) + 1
    else:
        wynik.ogolne.append(Uwaga(UWAGA, "BEZ_BAZY",
            "kontrola bez bazy LANTEKA - nie sprawdzono, czy elementy juz istnieja "
            "i jaka rute dostana"))
    ref_w_zamowieniu = {(r.get("PrdRef") or "").strip() for r in linie_zam}

    for p, wiersze_zrodlowe, ilosc_suma, rozbieznosci in scalone:
        w = Wiersz(poz=p, wiersze_zrodlowe=wiersze_zrodlowe, ilosc_suma=ilosc_suma)
        wynik.wiersze.append(w)

        # 1) referencja
        if not p.ref:
            w.dodaj(STOP, "BRAK_REFERENCJI", "pusta nazwa w kolumnie referencji")
            continue
        if len(p.ref) > MAX_REF:
            w.dodaj(STOP, "REFERENCJA_ZA_DLUGA",
                    "%d znakow, limit LANTEKA %d" % (len(p.ref), MAX_REF))
        blad_kod = cp1250_ok(p.ref)
        if blad_kod:
            w.dodaj(STOP, "ZNAK_SPOZA_CP1250", "XML idzie w windows-1250: %s" % blad_kod)
        if len(wiersze_zrodlowe) > 1:
            if rozbieznosci:
                w.dodaj(STOP, "DUPLIKAT_ROZNI_SIE",
                        "ta sama referencja w wierszach %s, ale rozne dane (%s)"
                        % (wiersze_zrodlowe, "; ".join(rozbieznosci)))
            else:
                w.dodaj(UWAGA, "SCALONY_Z_WIELU_WIERSZY",
                        "referencja z wierszy %s, ilosci razem %s, wgrywamy %s"
                        % (wiersze_zrodlowe, liczba_txt(ilosc_suma), liczba_txt(p.ilosc)))

        # 2) material i grubosc - domyslnie z REFERENCJI, kolumny sluza do kontroli
        w.material = material_lantek(p.gatunek) or ""
        if not p.gatunek:
            w.dodaj(STOP, "BRAK_GATUNKU",
                    "nie umiem odczytac gatunku - referencja '%s' nie ma drugiego czlonu"
                    % p.ref)
        elif not w.material:
            blisko = podpowiedz_material(p.gatunek, materialy_bazy)
            w.dodaj(STOP, "GATUNEK_BEZ_MAPOWANIA",
                    "gatunek '%s' (%s) nie ma odpowiednika w mapowanie.json%s"
                    % (p.gatunek, p.zrodlo,
                       ("; w kartotece LANTEKA jest: " + ", ".join(blisko)) if blisko else ""))
        elif materialy_bazy and w.material not in materialy_bazy:
            blisko = podpowiedz_material(w.material, materialy_bazy)
            w.dodaj(STOP, "MATERIAL_NIEZNANY_LANTEKOWI",
                    "material '%s' nie istnieje w kartotece LANTEKA%s"
                    % (w.material,
                       ("; najblizsze: " + ", ".join(blisko)) if blisko else ""))
        if not p.grubosc:
            w.dodaj(STOP, "BRAK_GRUBOSCI",
                    "nie umiem odczytac grubosci - referencja '%s' nie zaczyna sie "
                    "od liczby" % p.ref)
        if p.rozjazd_grubosci:
            w.dodaj(UWAGA, "GRUBOSC_ROZJAZD",
                    "referencja mowi %s, kolumna wykazu %s - wgrywamy %s (%s)"
                    % (liczba_txt(p.grubosc_ref), liczba_txt(p.grubosc_kol),
                       liczba_txt(p.grubosc), p.zrodlo))
        if p.rozjazd_gatunku:
            w.dodaj(UWAGA, "GATUNEK_ROZJAZD",
                    "referencja mowi '%s', kolumna wykazu '%s' - wgrywamy '%s' (%s)"
                    % (p.gatunek_ref, p.gatunek_kol, p.gatunek, p.zrodlo))

        # 3) ilosc
        if not p.ilosc:
            w.dodaj(STOP, "BRAK_ILOSCI", "ilosc pusta lub 0")
        elif p.ilosc_ref is not None and int(p.ilosc) != p.ilosc_ref:
            w.dodaj(UWAGA, "ILOSC_ROZJAZD",
                    "kolumna ilosci: %s, a w referencji '%dst'"
                    % (liczba_txt(p.ilosc), p.ilosc_ref))

        # 4) technologia i marszruta
        w.kod = p.kod
        w.kod_gnie = marszruta.gnie(w.kod)
        if not marszruta.znany(w.kod):
            w.dodaj(UWAGA, "KOD_TECHNOLOGII_NIEZNANY",
                    "kod '%s' spoza legendy - nie umiem przewidziec marszruty" % w.kod)
        if p.kod_ref is not None and p.kod_kolumna and \
                p.kod_ref.upper() != p.kod_kolumna.strip().upper():
            w.dodaj(UWAGA, "KOD_ROZJAZD",
                    "kolumna 'Giecie' mowi '%s', a referencja niesie '%s' - do LANTEKA "
                    "idzie referencja" % (p.kod_kolumna, p.kod_ref))

        if szablony_rut:
            r, kandydaci, opis = ruty.przewidz(szablony_rut, p.ref, p.grubosc, klasa=2)
            w.ruta = r.ref if r else ""
            w.marszruta = r.opis() if r else ""
            w.ruta_gnie = bool(r and any(o[2] == "Giecie" for o in r.operacje))
            if len(kandydaci) > 1:
                w.dodaj(UWAGA, "RUTA_NIEJEDNOZNACZNA",
                        "pasuje kilka rut (%s) - LANTEK wybierze sam"
                        % ", ".join(k.ref for k in kandydaci))
            if w.kod_gnie and not w.ruta_gnie:
                w.dodaj(UWAGA, "MARSZRUTA_BEZ_GIECIA",
                        "technologia '%s' mowi o gieciu, ale regula LANTEKA nada rute "
                        "'%s' (%s) - element pojdzie bez gietarki"
                        % (w.kod, w.ruta, w.marszruta or "brak operacji"))
            if w.ruta_gnie and not w.kod_gnie:
                w.dodaj(UWAGA, "MARSZRUTA_Z_GIECIEM",
                        "technologia '%s' nie mowi o gieciu, a LANTEK nada rute '%s'"
                        % (w.kod, w.ruta))

        # 5) plik DXF
        d = dopasowanie.get(p.ref, {"plik": None, "stan": "brak", "uwaga": ""})
        w.plik_dxf, w.stan_dxf = d["plik"], d["stan"]
        if d["stan"] == "brak":
            w.dodaj(STOP, "BRAK_DXF", "nie ma pliku '%s.dxf' we wskazanym folderze" % p.ref)
        elif d["stan"] == "kopie":
            # ten sam plik lezy w kilku wskazanych folderach - normalne, bo robimy
            # kopie robocze. Bierzemy z folderu wskazanego jako pierwszy.
            w.dodaj(UWAGA, "DXF_KOPIE_W_KILKU_FOLDERACH", d["uwaga"])
        elif d["stan"] == "kilka_roznych":
            w.dodaj(STOP, "DXF_ROZNE_WERSJE", d["uwaga"])
        elif d["stan"] == "inna_wielkosc_liter":
            w.dodaj(UWAGA, "DXF_INNA_WIELKOSC_LITER",
                    d["uwaga"] + " - plik pojdzie pod nazwa z wykazu")

        if w.plik_dxf and badaj_dxf:
            info = dxf_check.zbadaj(w.plik_dxf)
            w.dxf_info = info
            if info.otwarty is False:
                w.dodaj(STOP, "DXF_NIE_OTWIERA", info.blad)
            elif info.encji == 0:
                w.dodaj(STOP, "DXF_PUSTY", "plik nie zawiera zadnych elementow")
            elif not info.szer or not info.wys:
                w.dodaj(UWAGA, "DXF_BEZ_GABARYTU", "nie umiem zmierzyc gabarytu")

        # 6) baza: czy element juz jest
        d_baza = produkty.get(p.ref)
        w.w_bazie = d_baza
        w.marszruta_w_bazie = ""
        if operacje_bazy.get(p.ref):
            from . import lantek_db as db
            w.marszruta_w_bazie = db.marszruta_txt(operacje_bazy[p.ref])
        if d_baza:
            mat_b = (d_baza.get("DIS_MatRef") or "").strip()
            gr_b = d_baza.get("DIS_Thickness")
            rozne = []
            if w.material and mat_b and mat_b != w.material:
                rozne.append("material w bazie '%s', wgramy '%s'" % (mat_b, w.material))
            if p.grubosc and gr_b is not None and abs(float(gr_b) - float(p.grubosc)) > 0.01:
                rozne.append("grubosc w bazie %s, wgramy %s"
                             % (liczba_txt(gr_b), liczba_txt(p.grubosc)))
            if rozne:
                w.dodaj(STOP, "ELEMENT_INNY_W_BAZIE",
                        "element juz istnieje i rozni sie: " + "; ".join(rozne))
            else:
                w.dodaj(UWAGA, "ELEMENT_JUZ_W_BAZIE",
                        "element juz jest w kartotece (zalozony %s) - import go nadpisze"
                        % str(d_baza.get("CrtDate"))[:16])

        # 7) zamowienie sprzedazy
        if ordref and p.ref in ref_w_zamowieniu:
            w.dodaj(STOP, "JUZ_W_ZAMOWIENIU",
                    "element jest juz linia zamowienia '%s' - ponowne wgranie zdubluje "
                    "pozycje i zawyzy ilosc" % ordref)

        # 8) jawne operacje (opcja)
        if jawne_operacje and marszruta.znany(w.kod):
            try:
                w.poz.uwagi.append(marszruta.opis(w.kod, dokladaj_spawanie, dokladaj_ocynk))
            except Exception:
                pass

    wynik.materialy = zestawienie_materialow(wynik.wiersze, materialy_bazy)
    return wynik


# ----------------------------------------------------------------- kontrola PO

@dataclass
class WynikPo:
    wiersze: list = field(default_factory=list)
    werdykt: str = OK
    ordref: str = ""


def po(cn, wiersze_wgrane, ordref="") -> WynikPo:
    """Czy w bazie jest dokladnie to, co mielismy wgrac."""
    from . import lantek_db as db
    out = WynikPo(ordref=ordref)
    refy = [w.ref for w in wiersze_wgrane]
    produkty = db.produkty_po_ref(cn, refy)
    operacje = db.operacje_po_ref(cn, refy)
    linie = {(r.get("PrdRef") or "").strip(): r for r in
             (db.linie_zamowienia(cn, ordref) if ordref else [])}
    poziomy = []
    for w in wiersze_wgrane:
        d = produkty.get(w.ref)
        ops = operacje.get(w.ref, [])
        wpis = {"ref": w.ref, "jest": bool(d),
                "material": (d.get("DIS_MatRef") or "").strip() if d else "",
                "grubosc": d.get("DIS_Thickness") if d else None,
                "marszruta": db.marszruta_txt(ops), "operacji": len(ops),
                "oczekiwana": w.marszruta, "ma_giecie": any(o[3] == "Giecie" for o in ops),
                "mial_miec_giecie": w.kod_gnie,
                "linia": linie.get(w.ref), "uwagi": []}
        if not d:
            wpis["uwagi"].append((STOP, "elementu nie ma w kartotece"))
        else:
            if w.material and wpis["material"] and wpis["material"] != w.material:
                wpis["uwagi"].append((STOP, "material w bazie '%s', mial byc '%s'"
                                      % (wpis["material"], w.material)))
            if w.poz.grubosc and wpis["grubosc"] is not None and \
                    abs(float(wpis["grubosc"]) - float(w.poz.grubosc)) > 0.01:
                wpis["uwagi"].append((STOP, "grubosc w bazie %s, miala byc %s"
                                      % (wpis["grubosc"], w.poz.grubosc)))
            if w.kod_gnie and not wpis["ma_giecie"]:
                wpis["uwagi"].append((UWAGA, "brak gietarki w marszrucie (jest: %s)"
                                      % (wpis["marszruta"] or "pusta")))
        if ordref:
            if not wpis["linia"]:
                wpis["uwagi"].append((UWAGA, "brak linii w zamowieniu %s" % ordref))
            else:
                ilosc_b = float(wpis["linia"].get("Quantity") or 0)
                if w.poz.ilosc and abs(ilosc_b - float(w.poz.ilosc)) > 0.001:
                    wpis["uwagi"].append((STOP, "ilosc w zamowieniu %s, miala byc %s"
                                          % (liczba_txt(ilosc_b), liczba_txt(w.poz.ilosc))))
        poziom = max([p for p, _ in wpis["uwagi"]], key=lambda x: WAGA[x]) \
            if wpis["uwagi"] else OK
        wpis["poziom"] = poziom
        poziomy.append(poziom)
        out.wiersze.append(wpis)
    out.werdykt = max(poziomy, key=lambda p: WAGA[p]) if poziomy else OK
    return out
