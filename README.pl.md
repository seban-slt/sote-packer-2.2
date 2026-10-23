# SoTe Packer 2.2

Polski | [English](README.md)

SoTe Packer 2.2 to program do kompresji danych na Atari 8-bit autorstwa Adama Bieniasa, znanego jako SoTe / Slight.
Ta wersja pochodzi z 1994 roku.

Packer powstał jako narzędzie do naszego wewnętrznego użytku. Dopiero później został udostępniony scenie za darmo.
Wersją 2.2 (fast) pakowaliśmy dane do dema Overmind oraz artykuły do naszego magazynu dyskowego Barymag #2.
Bitter Reality korzystało z wcześniejszej wersji packera, z wolniejszym depackerem odczytującym dane bitowo.

Po latach wróciłem do zachowanych plików i rozpoczętej kiedyś analizy jego kodu.
Chciałem zrozumieć, jak działał, uporządkować źródła i móc znowu korzystać z tego formatu - tym razem także na współczesnym komputerze.

Z tej pracy powstał `sote_crunch.py`: narzędzie do pakowania i rozpakowywania danych zgodne z oryginalnym depackerem na Atari.
Potrafi odtworzyć sposób kompresji SoTe, ale oferuje też dokładniejsze wyszukiwanie powtórzeń i optymalny dobór sposobu ich zapisu, bez zmiany formatu danych.

W repo znajdziesz również skomentowane źródła packera i depackera, odtworzony program na Atari oraz opis tego, czego dowiedzieliśmy się podczas analizy.
Zgodność sprawdziliśmy między innymi na 69 oryginalnych plikach z Barymaga #2.

## Jak zacząć

Potrzebujesz Pythona 3.9 lub nowszego. Wystarczy jego biblioteka standardowa.
Trzy pliki z `tools/` muszą pozostać razem.
Polecenia wykonuj z głównego katalogu repozytorium.

Pakowanie surowych danych:

```sh
python3 -B tools/sote_crunch.py encode input.bin output.p22 \
  --optimal --window auto --extended-window --destination 0x2000 --stats
```

Rozpakowanie:

```sh
python3 -B tools/sote_crunch.py decode output.p22 restored.bin
```

Porównanie z wejściem:

```sh
cmp input.bin restored.bin
```

Za każdym razem podaj nową nazwę wyniku. Narzędzie nie nadpisuje plików.
Adres docelowy plus długość danych musi być mniejszy od `0x10000`.

Przy większych danych warto zamienić `python3` na `pypy3`.
PyPy potrafi mocno skrócić pakowanie, bez zmiany algorytmu.
Opcja `-B` wyłącza zapis plików pamięci podręcznej kodu bajtowego Pythona.
Nie jest przełącznikiem szybszej kompresji.

## Wybór sposobu pakowania

| Opcja | Działanie |
| --- | --- |
| Bez opcji trybu | Odtwarza algorytm wyszukiwania SoTe i oba przebiegi; wejście musi mieć mniej niż 36 864 bajty. |
| `--relaxed` | Zachowuje algorytm wyszukiwania i oba przebiegi, ale dopuszcza dłuższe dane i opcjonalnie większe okna. |
| `--optimal` | Sprawdza wszystkich kandydatów i dobiera tokeny według najmniejszego kosztu bitowego. |
| `--window auto` | Porównuje rozmiary bloków i wybiera najmniejszy. |
| `--extended-window` | Dopuszcza okna od 7 do 9 z `--optimal` albo `--relaxed`. |
| `--stats` | Po pakowaniu pokazuje statystyki wybranego bloku. |

Domyślnie narzędzie używa trybu historycznego, okna 1 i celu `0x8000`.
Tryb optymalny minimalizuje rozmiar przy kopiach długości od 2 do 255 bajtów. Ostatni token musi kończyć się dokładnie na końcu danych.
Nie minimalizuje czasu depakowania.

Narzędzie traktuje cały plik wejściowy jako surowe bajty.
Nie wczytuje segmentów XEX i nie tworzy samorozpakowującego się programu na Atari.
Wynik `.p22` zawiera nagłówek FAST i spakowane dane.

## Pliki i dokumentacja

| Ścieżka | Zawartość |
| --- | --- |
| [tools/sote_crunch.py](tools/sote_crunch.py) | Kompresor i dekompresor. |
| [tools/match_search.py](tools/match_search.py) | Pełne wyszukiwanie dopasowań i optymalny dobór tokenów. |
| [tools/sote_stats.py](tools/sote_stats.py) | Opcjonalne statystyki kompresji. |
| [src/sote_packer.xsm](src/sote_packer.xsm) | Skomentowana rekonstrukcja packera na Atari. |
| [src/sote_depacker.xsm](src/sote_depacker.xsm) | Skomentowany depacker długości 195 bajtów, w składni XASM. |
| [bin/sote_packer.xex](bin/sote_packer.xex) | Ponownie złożony packer na Atari. |
| [Instrukcja użytkownika](docs/USER_GUIDE.pl.md) | Polecenia, ograniczenia, użycie na Atari, budowanie i testy. |
| [Format danych](docs/FORMAT.pl.md) | Nagłówek, bity sterujące, długości i odległości. |
| [Wyszukiwanie](docs/SEARCH.pl.md) | Wyszukiwanie dopasowań u SoTe, programowanie dynamiczne i wybór offsetu. |
| [Ustalenia](docs/FINDINGS.pl.md) | Mapa programu, potwierdzone wyniki i otwarte pytania. |

## Co sprawdziliśmy

Dekoder Pythona odtworzył wszystkie 69 historycznych plików `.P22` z Barymaga #2.
Trzy oryginalne procedury 6502 dały te same dane we wszystkich 207 porównaniach.
[Ustalenia](docs/FINDINGS.pl.md) opisują przebieg tych testów i to, co potwierdzają.

Testy dołączone do repo uruchomisz tak:

```sh
python3 -B tests/verify.py
```

## Autorzy i licencja

Oryginalny packer, format danych i depacker: Adam Bienias (SoTe / Slight).
W oryginalnym programie autor występuje jako Soused Teat / Slight.

Zachowanie materiałów, historyczny disassembly i prowadzenie projektu:
Seban / Slight. Dalsza analiza, rekonstrukcja źródeł, dokumentacja
i narzędzia w Pythonie powstały z pomocą Codexa (model GPT-6 Astra).

Oryginalny program i jego źródła udostępniamy za zgodą Adama Bieniasa.

Kod i dokumentacja w tym repozytorium są dostępne na licencji MIT.
Pełne warunki znajdują się w pliku [LICENSE](LICENSE).
