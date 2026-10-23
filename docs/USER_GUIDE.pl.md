# Instrukcja użytkownika

[English](USER_GUIDE.md) | [Strona główna](../README.pl.md)

## Narzędzie Pythona

Polecenia wykonuj z głównego katalogu repozytorium. Trzy moduły w `tools/` muszą pozostać razem.
Nie wymagają dodatkowych pakietów. Narzędzie sprawdziliśmy z Pythonem 3.9 i 3.12.

Aby wybrać najmniejszy blok w trybie optymalnym, użyj:

```sh
python3 -B tools/sote_crunch.py encode input.bin output.p22 \
  --optimal --window auto --extended-window --destination 0x2000
```

Tryb optymalny działa według zasad opisanych w [Wyszukiwaniu dopasowań](SEARCH.pl.md).
Narzędzie pakuje dane dla każdego potrzebnego okna i porównuje rozmiary całych bloków.
Przy remisie wybiera mniejsze okno.
Tryb optymalny pomija rozszerzone okna, które przy danej długości wejścia nie dają nowych użytecznych odległości.

Odtworzenie historycznego algorytmu z oknem 3:

```sh
python3 -B tools/sote_crunch.py encode input.bin historical.p22 \
  --window 3 --destination 0x2000
```

Ten sam algorytm, ale z możliwością użycia dłuższych danych i większych okien:

```sh
python3 -B tools/sote_crunch.py encode input.bin relaxed.p22 \
  --relaxed --window auto --extended-window --destination 0x2000
```

Nie łącz `--optimal` z `--relaxed`.
Opcja `--extended-window` wymaga jednego z tych trybów.
Bez niej automatyczny wybór obejmuje okna od 1 do 6.
Tryb relaxed z rozszerzonymi oknami sprawdza wszystkie dziewięć, z uwzględnieniem sztucznej końcówki zer.

Przy rozpakowywaniu okno, długość wyniku i adres docelowy pochodzą z nagłówka:

```sh
python3 -B tools/sote_crunch.py decode input.p22 output.bin
```

Dekoder zapisuje same dane. Nie dodaje wypełnienia przed adresem docelowym.
Kończy po odtworzeniu zadeklarowanej liczby bajtów. Pomija nieprzeczytaną końcówkę pliku.
Odrzuca ucięte dane, odwołania poza już rozpakowane dane i nieobsługiwane wartości nagłówka.
Oryginalna procedura 6502 nie wykonuje takich kontroli wejścia.

## Ograniczenia i adresy

Narzędzie wiersza poleceń wymaga niepustego wejścia.
Tryb historyczny przyjmuje mniej niż `0x9000` bajtów. Tryby optimal i relaxed przyjmują do 65 535 bajtów.
W każdym trybie musi zachodzić:

```text
0 <= adres_docelowy < adres_docelowy + długość_wejścia < 65536
```

Adres końca równy `0x10000` też odpada.
Warunek końca w oryginalnym depackerze nie obsługuje tego przypadku.
Domyślny cel to `0x8000`, więc przy nim zmieści się najwyżej 32 767 bajtów.
Dla 44 026 bajtów pod `0x1006` użyj `--optimal` albo `--relaxed` oraz `--destination 0x1006`.

Adres docelowy jest polem nagłówka. Nie rezerwuje pamięci Atari.
Przed użyciem na Atari rozmieść spakowane dane, wynik, kod, zmienne ZP i stos.
Na początek użyj rozłącznych obszarów w zapisywalnej pamięci RAM.

| Okno | Bity odległości | Maksymalna odległość wstecz |
| ---: | ---: | ---: |
| 1 | 8 | 255 |
| 2 | 9 | 511 |
| 3 | 10 | 1 023 |
| 4 | 11 | 2 047 |
| 5 | 12 | 4 095 |
| 6 | 13 | 8 191 |
| 7 | 14 | 16 383 |
| 8 | 15 | 32 767 |
| 9 | 16 | 65 535 |

Każda odległość musi się też mieścić w już rozpakowanych danych.
Oryginalny interfejs udostępnia tylko okna od 1 do 6. Oryginalne depackery odczytują wszystkie dziewięć.

## Szybkość i statystyki

Aby użyć PyPy, zamień w poleceniu `python3` na `pypy3`.
JIT PyPy potrafi znacznie przyspieszyć te pętle Pythona.
Zysk zależy od danych i okna.
W projekcie zachowujemy prosty, czytelny algorytm. Nie ma wyszukiwania z użyciem tablicy haszującej ani równoległego pakowania.

Dodaj `--stats` do polecenia encode, aby zobaczyć liczby tokenów, długości kopii, odległości i koszt bitowy.
Raport pokazuje też nakładanie się kopii, nieczytaną końcówkę i skrócenie ostatniej kopii przez depacker.
Po kompresji odczytuje wybrany blok raz. Nie powtarza szukania ani obliczeń DP.
Bez `--stats` narzędzie nie liczy tego raportu.

## Użycie osobnego depackera

Dołącz [sote_depacker.xsm](../src/sote_depacker.xsm) po wybranym `ORG`.
Plik definiuje `depack` i etykiety pomocnicze. Używa komórek ZP od `$80` do `$85`.
Jeśli program zajmuje te komórki, zmień cztery wartości `EQU`.
Każdy wskaźnik wymaga dwóch kolejnych bajtów.

Wywołanie wygląda tak:

```asm
; packed_data points to the FAST header in RAM.

			cld
			ldy	<packed_data
			ldx	>packed_data
			jsr	depack
```

Procedura zmienia A, X, Y, znaczniki, swoje zmienne ZP i argumenty własnych instrukcji.
Każdy bajt wyniku zapisuje też do `COLBK`.
Kod musi leżeć w RAM pod adresem, dla którego został złożony.
Przeniesienie samych bajtów kodu wymaga poprawienia adresów bezwzględnych.
Po ostatnim bajcie procedura wraca do instrukcji za `JSR depack`.
Cel pochodzi z nagłówka. Wywołanie przekazuje tylko adres spakowanych danych.

To źródło daje 195 bajtów. Oryginalny packer dołącza inną procedurę, długości 204 bajtów, i ma własny relokator.

## Budowanie i testy

Do składania źródeł Atari zainstaluj osobno XASM.
Do uruchomienia gotowego pliku binarnego nie potrzebujesz asemblera.
Źródła używają prawdziwych tabulatorów o szerokości 8.
Ustawienia edytora zachowują wyrównanie etykiet, mnemoników, argumentów i komentarzy.

```sh
mkdir -p build
xasm src/sote_packer.xsm -o build/sote_packer.xex
cmp bin/sote_packer.xex build/sote_packer.xex
xasm tests/depacker_at_1800.xsm -o build/sote_depacker.xex
```

Ostatnie polecenie tworzy segment testowy pod `$1800`. To nie jest samodzielny program Atari.
XASM rozwiązuje ścieżkę dołączanego pliku względem głównego katalogu repozytorium.

Testy dołączone do repo:

```sh
python3 -B tests/verify.py
```

Z dodatkowym składaniem źródeł i porównaniem plików binarnych:

```sh
python3 -B tests/verify.py --xasm
```

Jeśli interpreter ma opcjonalny pakiet `py65`, można też wykonać depacker 6502:

```sh
python3 -B tests/verify.py --xasm --cpu
```

Test CPU używa płaskiej pamięci, bez ROM-u Atari, przerwań i DMA.
Nie sprawdza DOS-u, ekranu ani obsługi dysku.
Skrypt używa plików tymczasowych i usuwa je po teście.

## Oryginalny packer na Atari

Wczytaj `bin/sote_packer.xex` loaderem plików binarnych Atari.
Program korzysta z wewnętrznych procedur ROM-u XL/XE oraz CIO.
Rekonstrukcja zachowuje te zależności i historyczne błędy.

1. Podaj nazwę pliku wejściowego. Możesz też wpisać `*`, aby wyświetlić katalog, lub `#`, aby wrócić do DOS-u.
2. Jeśli chcesz odrzucić pierwsze sześć bajtów, trzymaj SHIFT podczas otwierania wejścia.
3. Podaj nazwę wyjścia i wybierz okno od 1 do 6.
4. Poczekaj na pierwszy przebieg. Zapisuje on plik pośredni pod nazwą wyjściową.
5. Odpowiedz na pytania o zapis. Drugi przebieg zastępuje plik pośredni końcowym wynikiem.

SHIFT tylko odrzuca sześć bajtów. Nie analizuje nagłówka XEX ani nie ładuje wielu segmentów.
Użyj innej nazwy wyjścia niż wejścia.

| Oryginalny komunikat | Znaczenie |
| --- | --- |
| `Save this as a file ?` | Wybór opakowania XEX. Odpowiedź `N` oznacza zapis surowego bloku FAST, a nie rezygnację z zapisu. |
| `Depack adress.` | Adres docelowy rozpakowanych danych. |
| `Adress of file location.` | Adres wczytania spakowanego bloku. |
| `Include depacker ?` | Dołączenie depackera długości 204 bajtów. |
| `Adress to run.` | Miejsce zapisu wektora wejścia depackera; domyślnie `INITAD`, `$02E2`. |
| `Run after depack ?` / `Where to jump ?` | Zastąpienie zwykłego powrotu skokiem pod podany adres. |

Adresy wpisuj jako cztery cyfry szesnastkowe: od `0` do `9` lub od `A` do `F`.
Parser adresu błędnie przyjmuje też część znaków interpunkcyjnych.
Flagi zapisu mogą zachować stan po poprzedniej operacji i spowodować zapis wadliwego pliku.
Przed kolejnymi zapisami lub skokiem po depakowaniu przeczytaj [opis potwierdzonych błędów](FINDINGS.pl.md).

Stały bufor wejściowy zaczyna się pod `$2B00`. Żądanie odczytu ma długość `0x9000` bajtów.
Nie gwarantuje to, że każde krótsze wejście zmieści się bezpiecznie w pamięci Atari.
Program potrzebuje też miejsca na dopełnienie, wynik i ekran.
Do dużych surowych bloków użyj narzędzia Pythona.
