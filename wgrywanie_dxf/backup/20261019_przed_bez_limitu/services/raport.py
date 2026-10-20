# -*- coding: utf-8 -*-
"""Raporty HTML i JSON - samodzielne pliki, otwierane dwuklikiem z folderu przebiegu.
Wzorowane na raport_html.py z integra-zakupy-wgraj (ten sam jezyk wizualny)."""
from __future__ import annotations

import html
import json
from datetime import datetime

from .kontrola import OK, STOP, UWAGA
from .wspolne import liczba_txt, sciezka

_CSS = """
:root{--zi:#0f7b3d;--zo:#b06a00;--cz:#b3261e;--tlo:#fff;--txt:#1a1a1a;--ram:#d8d8d8}
@media (prefers-color-scheme:dark){:root{--tlo:#16181c;--txt:#e8e8e8;--ram:#3a3d44}}
*{box-sizing:border-box}
body{font:15px/1.5 "Segoe UI",system-ui,sans-serif;margin:0;padding:24px;
     background:var(--tlo);color:var(--txt)}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
.sub{color:#888;font-size:13px;margin-bottom:18px}
.werdykt{padding:14px 18px;border-radius:8px;font-weight:700;font-size:18px;
         margin:16px 0;border:2px solid}
.w-OK{color:var(--zi);border-color:var(--zi);background:#0f7b3d14}
.w-UWAGA{color:var(--zo);border-color:var(--zo);background:#b06a0014}
.w-STOP{color:var(--cz);border-color:var(--cz);background:#b3261e14}
table{border-collapse:collapse;width:100%;margin:8px 0 16px;font-size:13px}
th,td{border:1px solid var(--ram);padding:4px 8px;text-align:left;vertical-align:top}
th{background:#8881;font-weight:600;position:sticky;top:0}
td.n{text-align:right;font-variant-numeric:tabular-nums}
tr.STOP{background:#b3261e1f}tr.UWAGA{background:#b06a001f}tr.OK{background:#0f7b3d12}
.tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;
     font-weight:700;color:#fff}
.t-OK{background:var(--zi)}.t-UWAGA{background:var(--zo)}.t-STOP{background:var(--cz)}
.karty{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}
.karta{border:1px solid var(--ram);border-radius:8px;padding:10px 16px;min-width:120px}
.karta b{display:block;font-size:26px;line-height:1.1}
.karta span{font-size:12px;color:#888}
code{background:#8881;padding:1px 5px;border-radius:4px;font-size:12px}
.przewin{overflow-x:auto}
"""


def _e(v):
    return html.escape("" if v is None else str(v))


def _tabela(naglowki, wiersze, klasy=None, prawo=()):
    out = ['<div class="przewin"><table><thead><tr>']
    out += ["<th>%s</th>" % _e(h) for h in naglowki]
    out.append("</tr></thead><tbody>")
    for i, w in enumerate(wiersze):
        k = ' class="%s"' % klasy[i] if klasy and klasy[i] else ""
        out.append("<tr%s>" % k)
        for j, c in enumerate(w):
            out.append("<td%s>%s</td>" % (' class="n"' if j in prawo else "",
                                          c if isinstance(c, _Raw) else _e(c)))
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


class _Raw(str):
    pass


def _tag(poziom):
    return _Raw('<span class="tag t-%s">%s</span>' % (poziom, _e(poziom)))


def _karty(pary):
    s = ['<div class="karty">']
    for etykieta, wartosc in pary:
        s.append('<div class="karta"><b>%s</b><span>%s</span></div>'
                 % (_e(wartosc), _e(etykieta)))
    s.append("</div>")
    return "".join(s)


def _dokument(tytul, podtytul, sekcje) -> str:
    body = []
    for nag, tresc in sekcje:
        if nag:
            body.append("<h2>%s</h2>" % _e(nag))
        body.append(tresc)
    return ("<!doctype html><html lang=pl><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style></head><body>"
            "<h1>%s</h1><div class=sub>%s</div>%s"
            "<div class=sub style='margin-top:32px'>wygenerowano %s &middot; "
            "wgrywanie DXF do LANTEKA</div></body></html>"
            % (_e(tytul), _CSS, _e(tytul), _e(podtytul), "".join(body),
               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


def sekcje_przed(wynik) -> list:
    lic = wynik.licznik()
    sekcje = [(None, '<div class="werdykt w-%s">%s</div>' % (wynik.werdykt, {
        OK: "OK - mozna wgrywac",
        UWAGA: "UWAGA - mozna wgrac po sprawdzeniu ponizszych pozycji",
        STOP: "STOP - sa pozycje, ktorych nie wolno wgrac",
    }[wynik.werdykt]))]
    sekcje.append((None, _karty([
        ("pozycji blachy", len(wynik.wiersze)), ("bez zastrzezen", lic[OK]),
        ("z uwaga", lic[UWAGA]), ("zablokowanych", lic[STOP]),
        ("do wgrania", len(wynik.do_wgrania)),
        ("plikow spoza wykazu", len(wynik.sieroty)),
        ("baza LANTEKA", "tak" if wynik.baza_dostepna else "nie"),
    ])))

    if wynik.ogolne:
        sekcje.append(("Uwagi ogolne", _tabela(
            ["poziom", "kod", "opis"],
            [[_tag(u.poziom), u.kod, u.opis] for u in wynik.ogolne],
            klasy=[u.poziom for u in wynik.ogolne])))

    if wynik.kody():
        sekcje.append(("Co sie powtarza", _tabela(
            ["kod", "ile pozycji"], [[k, v] for k, v in wynik.kody().items()], prawo=(1,))))

    if wynik.materialy:
        wiersze_m, klasy_m = [], []
        for m in wynik.materialy:
            ok_kart = m["w_kartotece"]
            klasy_m.append("" if ok_kart is None else ("OK" if ok_kart else "STOP"))
            wiersze_m.append([m["gatunek"], m["material"], m["pozycji"],
                              "?" if ok_kart is None else ("tak" if ok_kart else "NIE MA")])
        sekcje.append(("Materialy - co na co idzie", _tabela(
            ["gatunek z referencji", "MatRef w LANTEKU", "pozycji", "jest w kartotece"],
            wiersze_m, klasy=klasy_m, prawo=(2,))))

    wiersze, klasy = [], []
    for w in wynik.wiersze:
        klasy.append(w.poziom)
        wiersze.append([
            _tag(w.poziom), w.poz.wiersz, w.ref,
            "%s -> %s" % (w.poz.gatunek or "-", w.material or "?"),
            liczba_txt(w.poz.grubosc), liczba_txt(w.poz.ilosc), w.kod or "-",
            w.ruta or "-", w.marszruta or "-",
            "tak" if w.stan_dxf == "ok" else (w.stan_dxf or "brak"),
            ("%sx%s" % (w.dxf_info.szer, w.dxf_info.wys)) if w.dxf_info and w.dxf_info.szer else "-",
            "; ".join("%s: %s" % (u.poziom, u.opis) for u in w.uwagi),
        ])
    sekcje.append(("Pozycje", _tabela(
        ["", "w.", "referencja", "gatunek -> MatRef", "grub.", "ilosc", "kod", "ruta",
         "marszruta LANTEKA", "DXF", "gabaryt", "uwagi"],
        wiersze, klasy=klasy, prawo=(1, 4, 5))))

    if wynik.sieroty:
        sekcje.append(("Pliki DXF bez pozycji w wykazie (nie beda wgrane)",
                       "<p>" + _e(", ".join(wynik.sieroty[:200])) +
                       ("..." if len(wynik.sieroty) > 200 else "") + "</p>"))
    return sekcje


def zapisz_przed(wynik, folder, tytul_dodatkowy="") -> dict:
    f = sciezka(folder)
    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_p = f / ("PRZED_%s.html" % stempel)
    json_p = f / ("PRZED_%s.json" % stempel)
    podtytul = "wykaz: %s | folder DXF: %s | zamowienie: %s %s" % (
        tytul_dodatkowy, "", wynik.ordref,
        "(istnieje)" if wynik.zamowienie_istnieje else "(zostanie zalozone)")
    html_p.write_text(_dokument("Kontrola przed wgraniem", podtytul,
                                sekcje_przed(wynik)), encoding="utf-8")
    json_p.write_text(json.dumps({
        "werdykt": wynik.werdykt, "licznik": wynik.licznik(), "kody": wynik.kody(),
        "ordref": wynik.ordref, "zamowienie_istnieje": wynik.zamowienie_istnieje,
        "pierwsza_linia": wynik.pierwsza_linia,
        "baza_dostepna": wynik.baza_dostepna, "sieroty": wynik.sieroty[:500],
        "pozycje": [{
            "wiersz": w.poz.wiersz, "ref": w.ref, "poziom": w.poziom,
            "material": w.material, "grubosc": w.poz.grubosc, "ilosc": w.poz.ilosc,
            "kod": w.kod, "ruta": w.ruta, "marszruta": w.marszruta,
            "dxf": str(w.plik_dxf) if w.plik_dxf else None, "stan_dxf": w.stan_dxf,
            "uwagi": [{"poziom": u.poziom, "kod": u.kod, "opis": u.opis} for u in w.uwagi],
        } for w in wynik.wiersze],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"html": str(html_p), "json": str(json_p)}


def zapisz_wgranie(wynik_importu, folder, xml, elementow) -> str:
    f = sciezka(folder)
    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = f / ("WGRANIE_%s.html" % stempel)
    poziom = OK if wynik_importu.udany else (UWAGA if wynik_importu.uruchomiony else STOP)
    sekcje = [(None, '<div class="werdykt w-%s">%s</div>'
               % (poziom, wynik_importu.podsumowanie()))]
    sekcje.append((None, _karty([
        ("elementow", elementow), ("polecen", wynik_importu.polecen),
        ("ok", wynik_importu.ok), ("ostrzezen", wynik_importu.ostrzezen),
        ("BLEDOW", wynik_importu.bledow), ("czas [s]", wynik_importu.czas_s)])))
    sekcje.append(("Plik XML", "<p><code>%s</code></p>" % _e(xml)))
    if wynik_importu.log:
        sekcje.append(("Log importera", "<p><code>%s</code></p>" % _e(wynik_importu.log)))
    if wynik_importu.komunikaty:
        sekcje.append(("Komunikaty importera", _tabela(
            ["komunikat"], [[k] for k in wynik_importu.komunikaty])))
    sekcje.append(("Polecenie", "<p><code>%s</code></p>"
                   % _e(" ".join(wynik_importu.polecenie))))
    p.write_text(_dokument("Wgranie do LANTEKA",
                           "ostrzezenia typu 'already exists ... update is executed' sa normalne",
                           sekcje), encoding="utf-8")
    return str(p)


def zapisz_po(wynik_po, folder) -> dict:
    f = sciezka(folder)
    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_p = f / ("PO_%s.html" % stempel)
    json_p = f / ("PO_%s.json" % stempel)
    zgodne = sum(1 for w in wynik_po.wiersze if w["poziom"] == OK)
    z_gieciem = sum(1 for w in wynik_po.wiersze if w["ma_giecie"])
    sekcje = [(None, '<div class="werdykt w-%s">%s</div>' % (wynik_po.werdykt, {
        OK: "OK - w bazie jest to, co mialo byc",
        UWAGA: "UWAGA - sa roznice do obejrzenia",
        STOP: "STOP - baza nie zgadza sie z wykazem",
    }[wynik_po.werdykt]))]
    sekcje.append((None, _karty([
        ("sprawdzonych", len(wynik_po.wiersze)), ("zgodnych", zgodne),
        ("z gietarka w marszrucie", z_gieciem),
        ("zamowienie", wynik_po.ordref or "-")])))
    wiersze, klasy = [], []
    for w in wynik_po.wiersze:
        klasy.append(w["poziom"])
        linia = w["linia"]
        wiersze.append([
            _tag(w["poziom"]), w["ref"], "tak" if w["jest"] else "NIE",
            w["material"], liczba_txt(w["grubosc"]),
            w["marszruta"] or "(brak)", "tak" if w["ma_giecie"] else "nie",
            "tak" if w["mial_miec_giecie"] else "nie",
            (liczba_txt(linia.get("Quantity")) if linia else "-"),
            "; ".join("%s: %s" % (p, o) for p, o in w["uwagi"]),
        ])
    sekcje.append(("Pozycje w bazie", _tabela(
        ["", "referencja", "w kartotece", "material", "grub.", "marszruta",
         "gietarka", "miala byc", "ilosc w zam.", "uwagi"],
        wiersze, klasy=klasy, prawo=(4, 8))))
    html_p.write_text(_dokument("Kontrola po wgraniu", "odczyt z bazy LANTEKA",
                                sekcje), encoding="utf-8")
    json_p.write_text(json.dumps({
        "werdykt": wynik_po.werdykt, "ordref": wynik_po.ordref,
        "wiersze": [{k: (str(v) if k == "linia" else v) for k, v in w.items()}
                    for w in wynik_po.wiersze],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"html": str(html_p), "json": str(json_p)}
