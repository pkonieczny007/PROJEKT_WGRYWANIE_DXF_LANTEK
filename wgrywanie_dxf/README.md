# Wgrywanie DXF do LANTEKA (Sheet Parts)

Aplikacja Flask: wskazujesz **wykaz roboczy** i **folder(y) z plikami DXF**, ona sprawdza
komplet, składa XML i wgrywa do LANTEKA przez **PowerSync** (`XmlImporter.exe`).
Zastępuje ręczne makro `Lantek XLS2XML - Aggregate_v7.xlsm`.

Prototyp — zbudowany 18.09.2026. Do bazy pisze wyłącznie krok „Wgraj", i tylko po
zaznaczeniu potwierdzenia.

## Dlaczego powstała — i dlaczego marszruta wchodziła sama „Laser"

To jest najważniejsze ustalenie tego projektu, potwierdzone na bazie produkcyjnej
i eksperymentem na żywym elemencie:

**LANTEK nadaje marszrutę sam, regułą ruty, która czyta pole `UData8` produktu.**
Szablony rut leżą w `MMNN_PPOO_00000100`, a warunki w kolumnie `DIS_Rules`:

| ruta | warunek | operacje |
|---|---|---|
| `L` (domyślna) | grubość ≤ 15, `UData8` bez `S` i bez `G` | 2D Cut |
| `L+G` | `UData8` zawiera `_G_`, grubość ≤ 15 | 2D Cut → Giecie |
| `P+G` | `UData8` zawiera `_G_`, grubość > 15 | 2D Cut → Giecie |
| `L+G+S` | `UData8` zawiera `GS`, grubość ≤ 15 | 2D Cut → Giecie |
| `L+S`, `L+SO`, `P`, `P+S` | odpowiednio `_S_`, `_SO_` | 2D Cut |

Lantek Expert wpisuje do `UData8` **pełną referencję elementu** — dlatego u niego
marszruta wchodzi poprawnie (w bazie 20 363 elementy z rutą `L+G`).

Makro XLS2XML wysyłało `UData1`…`UData8` **puste** (351 z 353 plików w
`C:\Lantek\importxml`). Bez tego pola żaden warunek nie pasuje i element dostaje rutę
domyślną `L`, czyli **sam laser**.

Druga, niezależna pułapka: **jawne `PRODUCT OPERATIONS` nie utrzymują się** przy
elemencie, który dostaje geometrię. Importer sortuje polecenia po tabelach, więc
`IMPORTGEO` zawsze wykonuje się po operacjach i przebudowuje marszrutę. Z 400 elementów
wgranych importem, mających geometrię i pełną marszrutę, **399 miało gięcie dopisane
ręcznie** w Lantek Expert.

**Dlatego ta aplikacja wysyła `UData8 = PrdRef` i nie wpisuje operacji na siłę.**
Potwierdzone 18.09.2026: element `10_S235_test-giecie_GS_` → ruta `L+G` →
marszruta `2D Cut → Giecie`, mimo że ma geometrię.

## Uruchomienie

```bash
cp .env.example .env          # uzupełnij hasło do bazy, jeśli jest wymagane
pip install -r requirements.txt
python app.py                 # http://127.0.0.1:5059/dxf/
```

Aplikacja musi widzieć `C:\Lantek\System\Common\XmlImporter.exe` oraz katalog
`C:\Lantek\importxml\DXF`, czyli działa na maszynie z LANTEKIEM. Wszystkie ścieżki
siedzą w `.env` / `config.py`, więc da się ją przenieść na serwer.

## Przebieg pracy

1. **Zlecenie** — wpisujesz `NN_XXXX` (np. `82_1129`), aplikacja proponuje wykaz roboczy
   z Technologii i wszystkie foldery z plikami DXF (Technologia, `tmp\TMP_DXF_...`,
   wyniki ekstraktora). Folder wybierasz sam, można kilka — przy tej samej nazwie pliku
   wygrywa folder wskazany wyżej.
2. **Kontrola przed wgraniem** — nic nie zapisuje. Raport `PRZED_*.html` + `.json`.
3. **XML** — kopiuje pliki DXF tam, gdzie widzi je LANTEK, i składa `SheetParts_*.xml`.
4. **Wgranie** — `XmlImporter.exe`, czekanie na log, log ląduje w folderze przebiegu.
5. **Kontrola po wgraniu** — odczyt z bazy: czy elementy są, z jakim materiałem
   i grubością, **jaką dostały marszrutę** i czy ilości w zamówieniu się zgadzają.

Wyniki każdego przebiegu: `data/<NN_XXXX>_<data>_<godzina>/`.
Dziennik wszystkich wgrań: `data/rejestr_wgran.jsonl`.

## Co sprawdza kontrola

| kod | poziom | znaczenie |
|---|---|---|
| `FORMULA_NIEPRZELICZONA` | STOP | wykaz ma formuły bez wyniku — otwórz i zapisz w Excelu |
| `BRAK_REFERENCJI` | STOP | pusta nazwa robocza |
| `REFERENCJA_ZA_DLUGA` | STOP | ponad 40 znaków (`PrdRef` to `nvarchar(40)`) |
| `ZNAK_SPOZA_CP1250` | STOP | XML idzie w windows-1250 |
| `DUPLIKAT_ROZNI_SIE` | STOP | ta sama referencja, ale inna grubość/gatunek/technologia |
| `GATUNEK_BEZ_MAPOWANIA`, `MATERIAL_NIEZNANY_LANTEKOWI` | STOP | materiału nie ma w kartotece |
| `BRAK_GRUBOSCI`, `BRAK_ILOSCI` | STOP | grubość 0 blokuje zapis produktu |
| `BRAK_DXF`, `DXF_NIE_OTWIERA`, `DXF_PUSTY` | STOP | plik geometrii |
| `DXF_ROZNE_WERSJE` | STOP | ta sama nazwa w dwóch folderach, różny rozmiar |
| `ELEMENT_INNY_W_BAZIE` | STOP | element już jest, ale z innym materiałem/grubością |
| `JUZ_W_ZAMOWIENIU` | STOP | element jest już linią tego zamówienia |
| `MARSZRUTA_BEZ_GIECIA` | UWAGA | technologia mówi o gięciu, a reguła LANTEKA go nie nada |
| `SCALONY_Z_WIELU_WIERSZY` | UWAGA | referencja powtórzona w wykazie, scalona w jedną pozycję |
| `DXF_KOPIE_W_KILKU_FOLDERACH` | UWAGA | ten sam plik w kilku wskazanych folderach |
| `ILOSC_ROZJAZD` | UWAGA | kolumna ilości ≠ człon `Nst` w referencji |
| `KOD_ROZJAZD` | UWAGA | kolumna `Gięcie` ≠ kod w referencji (do LANTEKA idzie referencja) |
| `ELEMENT_JUZ_W_BAZIE` | UWAGA | import go nadpisze |

## Marszruta — kiedy reguła LANTEKA nie wystarcza

Reguły mają realne luki, sprawdzone na 2000 elementów:

- kod **`SG`** (odwrócona kolejność) — brak reguły, wchodzi `L` bez gięcia,
- kody **`W` / `WS`** (walcowanie) — brak reguły, wchodzi `L`,
- **`GSO` przy grubości > 15** — reguła `P+G+S` sprawdza `UData1` zamiast grubości,
- kody spoza legendy, np. `MG`.

Dla takich pozycji zaznacz „przygotuj poprawkę marszruty". Powstanie drugi plik
`Marszruta_*.xml` (kasuje marszrutę i wpisuje ją od nowa) — **wgrywany osobno, po
imporcie głównym**. To utarty wzorzec: w logach LANTEKA jest 937 takich usunięć, zero błędów.

## Przewidywanie marszruty

Aplikacja czyta reguły z bazy i przewiduje rutę przed wgraniem. Sprawdzone na 2000
elementów z nadaną rutą: **99,9% trafień** co do obecności gięcia, bez ani jednego
przeoczenia (nigdy nie powie „bez gięcia", gdy LANTEK gięcie nada). Nazwa ruty bywa
inna niż przewidziana, ale operacje te same — ruty `L`, `L+S`, `L+SO`, `P` mają
identyczną marszrutę (`2D Cut`), więc realnie różnicuje je tylko gięcie.

## Pułapki, które już zapłaciliśmy

- **`LineNum` w zamówieniu** — klucz kolizji to `(OrdRef, LineNum)`, a kolizja
  **nadpisuje linię** (49 udokumentowanych przypadków). Numerację kontynuujemy po
  `max(LineNum)`, nigdy od 1.
- **Surowy `&` w wartości** psuje cały plik — import kończy się na 0 poleceń.
  Generator escapuje `& < > "`, makro tego nie robiło.
- **`Length` i `Width` > 0** przełączają geometrię na prostokąt parametryczny i DXF jest
  ignorowany. Nie wysyłamy tych pól.
- **Ostrzeżenie `already exists ... update is executed`** jest normalne. Liczy się
  `Commands with error`.
- **Brak linii gięcia w pliku DXF nie jest błędem** — produkcyjne DXF z bazy nie mają
  żadnych oznaczeń gięcia (warstwa `0`/`L`/`51`, kolor 7). Rysujemy je tylko przy P/L
  albo gięciu pod skosem. Dlatego ta kontrola jest wyłącznie informacyjna.
- **Ścieżki UNC w kodzie zapisujemy ukośnikami w przód** (`//QNAP-ENERGO/...`).
  Wersja z backslashami gubi znak przy przepisywaniu pliku i `Path` widzi `\SERWER`.
- **Podfolder w `GeometryPath`** — wszystkie 14 962 historyczne importy wskazywały
  pliki płasko w `DXF\`. Kopiujemy do podfolderu per zlecenie (pełna ścieżka w XML).
  Gdyby import zgłosił `Cannot find geometry file`, ustaw `DXF_PODFOLDER=0` w `.env`.

## Pliki

```
app.py                     uruchomienie, port 5059
config.py / .env           ścieżki LANTEKA, dostęp do bazy, korzenie do propozycji
mapowanie.json             materiały, kody technologii, aliasy kolumn wykazu
modules/dxf/routes.py      pięć kroków przebiegu
services/wykaz.py          czytanie wykazu roboczego (pierwsza zakładka, po nagłówkach)
services/dxf_check.py      dopasowanie plików, gabaryt, kontrola otwieralności
services/ruty.py           reguły rut LANTEKA + przewidywanie marszruty
services/marszruta.py      kod technologii -> operacje
services/kontrola.py       reguły PRZED i PO
services/xml_sheetparts.py generator XML (cp1250, CRLF, escapowanie)
services/powersync.py      XmlImporter.exe + odczyt logu
services/lantek_db.py      baza LANTEKA — WYŁĄCZNIE SELECT
services/raport.py         raporty HTML/JSON
services/zlecenie.py       propozycje po numerze zlecenia, rejestr wgrań
testy/                     skrypty sprawdzające (uruchamiane ręcznie)
```

## Testy

```bash
python testy/t_wykaz.py              # parser wykazu na przykładzie 82_1129
python testy/t_xml_generator.py      # nasz XML kontra XML makra
python testy/t_ruty_giecie.py        # trafność przewidywania marszruty (baza)
python testy/t_kontrola_e2e.py 82_1129
python testy/t_e2e_flask.py 82_1129  # cały przebieg do XML, bez wgrywania
```

## Stan na 18.09.2026 - potwierdzone dzialanie

Pierwsze wgranie z aplikacji, zlecenie testowe `199_9999`: **10 polecen, 0 bledow**.
Trzy elementy w kartotece, kazdy z ruta `L+G` i marszruta `2D Cut -> Giecie`,
zamowienie `199_9999_BLACHY` zalozone z trzema liniami. Podfolder w sciezce
geometrii (`C:\Lantek\importxml\DXF99_9999\...`) zadzialal bez zastrzezen.

## Czego jeszcze nie ma

- **Sprawdzanie daszków** — pole w formularzu jest, ale wyłączone. Daszek to blacha,
  do której dochodzą otwory pod uniwersalną giętą nakładkę; stare pliki z bazy ich nie
  mają. Definicja do doprecyzowania.
- Wgrywanie na **prawdziwym zleceniu** — dotąd tylko zlecenie testowe `199_9999`
  (3 elementy). Kontrola po wgraniu (krok 4) nie była jeszcze klikana w aplikacji.
