# PROJEKT: wgrywanie DXF do LANTEKA

Narzędzie zastępujące ręczne makro Excela `Lantek XLS2XML - Aggregate_v7.xlsm`.
Wskazujemy **wykaz roboczy** i **folder(y) z plikami DXF** → kontrola → XML →
wgranie przez **PowerSync** (`XmlImporter.exe`) → kontrola w bazie.

Kod: [`wgrywanie_dxf/`](wgrywanie_dxf/) (Flask, port 5059, `python app.py` → `/dxf/`).
Pełna dokumentacja użytkowa: [`wgrywanie_dxf/README.md`](wgrywanie_dxf/README.md).
Materiał źródłowy (makra, przykładowe XML, wykazy): [`kontekst/`](kontekst/).

Start prac: 18.09.2026. Stan: **działający prototyp, potwierdzony end-to-end**.

Pierwsze prawdziwe wgranie z aplikacji, 18.09.2026 13:05, zlecenie testowe `199_9999`:
10 poleceń, **0 błędów**, 3 elementy w kartotece, wszystkie z rutą `L+G` i marszrutą
`2D Cut → Giecie`, zamówienie `199_9999_BLACHY` założone z trzema liniami.
Przy okazji potwierdzone, że **podfolder w ścieżce geometrii działa**
(`C:\Lantek\importxml\DXF\199_9999\...`) — importer nie zgłosił żadnego błędu.

---

## ZASADA NR 1 — marszruta idzie przez pole UData8, nie przez operacje

To jest sedno całego projektu. **LANTEK nadaje marszrutę sam**, regułą ruty, która
czyta pole `UData8` produktu. Szablony rut siedzą w `MMNN_PPOO_00000100`, warunki
w kolumnie `DIS_Rules`:

| ruta | warunek | operacje |
|---|---|---|
| `L` (domyślna) | grubość ≤ 15, `UData8` bez `S` i bez `G` | 2D Cut |
| `L+G` | `UData8` zawiera `_G_`, grubość ≤ 15 | 2D Cut → Giecie |
| `P+G` | `UData8` zawiera `_G_`, grubość > 15 | 2D Cut → Giecie |
| `L+G+S` | `UData8` zawiera `GS`, grubość ≤ 15 | 2D Cut → Giecie |
| `L+S`, `L+SO`, `P`, `P+S` | `_S_`, `_SO_` | 2D Cut |

Lantek Expert wpisuje do `UData8` **pełną referencję** — dlatego u niego marszruta
wchodzi poprawnie (w bazie 20 363 elementy z rutą `L+G`).

Makro XLS2XML wysyłało `UData1`…`UData8` **puste** (351 z 353 plików w
`C:\Lantek\importxml`), więc żaden warunek nie pasował i element dostawał rutę
domyślną `L` = **sam laser**. To była przyczyna skargi „marszruta wchodzi tylko Laser".

**Druga pułapka:** jawne `PRODUCT OPERATIONS` w XML **nie utrzymują się** przy
elemencie z geometrią. Importer sortuje polecenia po tabelach, więc `IMPORTGEO`
zawsze wykonuje się po operacjach i przebudowuje marszrutę. Z 400 elementów
wgranych importem, mających geometrię i pełną marszrutę, **399 miało gięcie
dopisane ręcznie** w Expercie.

→ **Generator zawsze ustawia `UData8 = PrdRef` i nie wpisuje operacji na siłę.**
Potwierdzone na żywym elemencie `10_S235_test-giecie_GS_` → ruta `L+G` →
marszruta `2D Cut → Giecie`, mimo geometrii.

Podmiana marszruty (gdy reguła nie nada gięcia) wymaga `DELETE` na
`PRODUCT OPERATIONS` + ponowny import, w **osobnym przebiegu** — wzorzec z 937
udanych usunięć w logach LANTEKA. Realizuje to `zbuduj_marszrute()`.

---

## ZASADA NR 2 — grubość i gatunek czytamy z REFERENCJI

Referencja ma postać
`{grubość}_{gatunek}_{Zeinr}_p{Posn}_{N}st_{TECHNOLOGIA}_{4 cyfry zlecenia}_{index}`.

- **grubość** = człon 1, **gatunek** = człon 2,
- **technologia** = człon **po członie ilości** (`Nst`), nigdy „sztywno szósty" —
  bywa dodatkowy człon wariantu (`2_VER_SL10348893_p1_A_1st_GS_8241D_`),
- człon ilości musi mieć literę (`2st`, `4s`, `188st`); sam ciąg cyfr nią nie jest,
  bo numer rysunku bez prefiksu `SL` zostałby wzięty za ilość.

Kolumny `grubosc_poprawiona` / `gatunek_poprawiony` istnieją **tylko** w wykazach
zrobionych przez `/wykaz-roboczy` — dlatego nie są źródłem prawdy. Kontrola i tak
porównuje oba źródła i zgłasza rozjazd. Przełącznik źródła jest na stronie startowej.

Gatunek jest tłumaczony na `MatRef`, który **musi istnieć w kartotece LANTEKA**
(`DIS_MMTT_MMTT_00000100`). Mapowanie w `mapowanie.json` — 33 pozycje, wszystkie
zweryfikowane wobec bazy, zgodność z 3864 z 4000 ostatnich blach.

---

## ZASADA NR 3 — do bazy piszemy wyłącznie przez XmlImporter

`services/lantek_db.py` wykonuje **tylko SELECT**. Nigdy INSERT/UPDATE/DELETE.
Jedyny tor zapisu to `C:\Lantek\System\Common\XmlImporter.exe`, uruchamiany
w kroku „Wgraj" po zaznaczeniu potwierdzenia.

Baza: `192.168.13.5\LANTEKSQL2019`, `Energosolver_DB_0_9`, ODBC Driver 17.
Polskie znaki w zapytaniach **tylko przez parametry pyodbc** — literał bez prefiksu
`N` po cichu zwraca 0 wierszy.

Tabele: `PPRR_PPRR_00000100` produkty, `MMNN_PPOO_00000100` szablony rut,
`MMNN_PPOO_00000200` marszruty produktów, `SSAA_SSOO_00000100/200` zamówienia.

---

## Pułapki, które już zapłaciliśmy

- **`LineNum` w zamówieniu** — klucz kolizji to `(OrdRef, LineNum)`, a kolizja
  **nadpisuje linię** (49 udokumentowanych przypadków w logach). Numerację
  kontynuujemy po `max(LineNum)`, nigdy od 1.
- **Surowy `&` w wartości** psuje cały plik — import kończy się na 0 poleceń.
  Generator escapuje `& < > "`; makro tego nie robiło.
- **`Length` i `Width` > 0** przełączają geometrię na prostokąt parametryczny
  i DXF jest ignorowany. Nie wysyłamy tych pól.
- **Kodowanie XML to windows-1250**, CRLF, bez deklaracji XML. Znak spoza cp1250
  psuje import — kontrola to wyłapuje.
- **`PrdRef` i `OrdRef` to `nvarchar(40)`** — dłuższe są ucinane.
- **Ścieżki UNC w kodzie zapisujemy ukośnikami w przód** (`//QNAP-ENERGO/...`).
  Wersja z backslashami gubi znak przy przepisywaniu pliku przez powłokę i `Path`
  widzi `\SERWER` — katalog od korzenia, którego nie ma. Kosztowało to jeden fałszywy
  „nie znajduje folderu zlecenia".
- **Nie przekazuj ścieżek z polskimi znakami przez heredoc powłoki** — zapisz skrypt
  do pliku `.py` i uruchom.
- **Ostrzeżenie `already exists ... update is executed`** jest normalne. Liczy się
  `Commands with error`.
- **Brak linii gięcia w DXF nie jest błędem** — produkcyjne pliki z bazy nie mają
  żadnych oznaczeń gięcia (warstwa `0`/`L`/`51`, kolor 7). Rysujemy je tylko przy P/L
  albo gięciu pod skosem. Ta kontrola jest wyłącznie informacyjna.
- **`openpyxl` nie liczy formuł** — wykaz czytamy z `data_only=True`. Pusta referencja
  przy formule znaczy „wykaz niezapisany w Excelu", nie „brak danych".
- **Kolumny wykazu szukamy po nagłówku, nie po literze**; przy duplikacie nazwy
  wygrywa kolumna **najbardziej z lewej** (rozbicie `Bezeichnung` kopiuje nagłówek w prawo).
- **Ta sama referencja w kilku wierszach wykazu** to norma (część wymieniona przy
  kilku złożeniach) — scalamy w jedną pozycję. Na 82_1129: 108 takich referencji,
  żadna nie różniła się materiałem ani grubością.

---

## Co zostało do zrobienia

1. **Wgranie na prawdziwym zleceniu** — dotąd tylko zlecenie testowe `199_9999`
   (3 elementy). Kolejny krok: jedno realne zlecenie, najlepiej małe.
2. **Kontrola po wgraniu (krok 4)** nie została jeszcze uruchomiona z aplikacji —
   weryfikację 199_9999 robiliśmy skryptem `testy/t_po_wgraniu_199.py`.
3. **Daszki** — pole w formularzu jest, wyłączone. Daszek to blacha, do której
   dochodzą otwory pod uniwersalną giętą nakładkę; stare pliki z bazy ich nie mają.
   Definicja do doprecyzowania z technologiem.
4. **Luki w regułach LANTEKA** (sprawdzone na 2000 elementów): kody `SG`, `W`, `WS`
   oraz `GSO` przy grubości > 15 nie dostają gięcia. Dla nich służy poprawka marszruty.
   Decyzja użytkownika: `W`, `WS`, `WSO` mają być traktowane jak gięcie.

---

## Jak pracować z tym projektem

```bash
cd wgrywanie_dxf
cp .env.example .env          # .env NIE trafia do repozytorium
python app.py                 # http://127.0.0.1:5059/dxf/
```

Testy (uruchamiane ręcznie, wymagają dostępu do bazy i sieci):

```bash
python testy/t_wykaz.py              # parser wykazu na 82_1129
python testy/t_xml_generator.py      # nasz XML kontra XML makra
python testy/t_materialy.py          # mapowanie gatunków wobec kartoteki LANTEKA
python testy/t_ruty_giecie.py        # trafność przewidywania marszruty (99,9%)
python testy/t_kontrola_e2e.py 82_1129
python testy/t_e2e_flask.py 82_1129  # cały przebieg do XML, bez wgrywania
```

Źródła wiedzy, z których korzystaliśmy: SecondBrain
(`\\Qnap-energo\baza\.data\SecondBrain`), narzędzia `integra-zakupy-wgraj`
(`\\Qnap-energo\baza\.data\python\`), serwis zakupów `PROJEKT_ETAPY`
(`\\QNAP-ENERGO\Technologia\Python\PROJEKT_ETAPY`), EKSTRAKTOR_DXF V3
(`C:\Python_CLaude\EKSTRAKTOR_DXF\EKSTRAKTOR_DXF-home-V3`).
