# Ustalenia i dowody

[English](FINDINGS.md) | [Strona główna](../README.pl.md)

Analiza opiera się na oryginalnym XEX-ie, zachowanym źródle depackera, historycznym disassembly i wynikach testów wykonania.
Komentarze i etykiety objaśniają te dowody. Jeśli nie zaznaczono inaczej, nie są symbolami z oryginalnego źródła autora.

## Mapa programu

Oryginalny XEX ładuje wektor startu pod `$02E0`, dane pod `$0480` do `$06FB` oraz kod pod `$2000` do `$2A67`.
Stały bufor danych zaczyna się pod `$2B00`.

| Część | Funkcja |
| --- | --- |
| Start i obsługa ekranu | Przygotowanie edytora, komunikatów i informacji o postępie kompresji. |
| Procedury CIO | Otwieranie, odczyt, zapis i zamykanie plików; katalog i powrót do DOS-u. |
| Przygotowanie wejścia | Odczyt bajtów pod `$2B00`, opcjonalne odrzucenie sześciu bajtów, dopisanie 512 zer. |
| Wybór okna | Zamiana wyboru od 1 do 6 na `k=0..5`. |
| `pack_loop` i wyszukiwanie dopasowań | Szukanie we wcześniejszych danych, z pomijaniem kandydatów, oraz wybór kopii albo literału. |
| Zapis bitów pierwszego przebiegu | Zapis tokenów jako ciągłego strumienia bitów do pliku wyjściowego. |
| `finish_1st_pass`, `save_as_file` | Wybór raw FAST albo XEX, adresów, depackera i końcowego skoku. |
| `second_pass` | Odczyt pliku pośredniego i przestawienie pól na FAST w buforze danych. |
| Wbudowany depacker | Odtwarzanie bajtów ze strumienia FAST; 204 bajty kodu dołączanego do wyniku. |
| Relokacja i końcowy zapis | Poprawienie adresów dołączonego depackera, zapis opakowania i wektora. |

Komórki strony zerowej pełnią różne role w kolejnych etapach.
Skomentowane źródło grupuje aliasy według etapu i każdemu przypisuje fizyczny adres.
`EQU` nie tworzy nowej zmiennej ani nie zachowuje poprzedniej wartości.
Komentarze `(variable reused)` oznaczają współdzielone miejsce, także częściowo nakładające się słowa.

## Potwierdzone wyniki

- Zrekonstruowany packer daje dokładnie oryginalny XEX długości 3316 bajtów.
- Historyczny enkoder Pythona odtworzył wyniki obu przebiegów oryginalnego packera w 66 próbach: 11 wejść razy sześć okien.
- Osobne źródło depackera daje 195 bajtów zgodnych z zachowaną procedurą złożoną pod `$1800`.
- Oryginalne depackery odczytują rozszerzone odległości do 16 bitów. Oryginalny interfejs oferuje od 8 do 13 bitów.
- FAST ma po jednym bicie flagi na literał za pierwszym. Kody długości są stałe, a odległości mają stałą szerokość.
- Drugi przebieg zmienia rozmieszczenie pól. Nie wyszukuje ponownie dopasowań.
- Bufor wejścia ma stały adres. Packer nie wyznacza go z `MEMLO`.

Te fakty potwierdzają komentarze o dwóch przebiegach, czytnikach bitów, drzewie długości, odległościach i relokacji.
Dokładny zapis oryginalnego źródła i nazwy zmiennych autora pozostają nieznane.

SHA-256 oryginalnego XEX-a i odtworzonego `bin/sote_packer.xex`:

```text
127dd1d0cb71c56a449eeeda4365e099519ed03b5c2eef75b05401e5a7f54cd4
```

SHA-256 samych 195 bajtów osobnego depackera, złożonego pod `$1800`:

```text
cee39f7651763a583eaec60a8c176fa2a770243c916d7090fa809ce668d0af5c
```

## Poprawione interpretacje i zachowane błędy

**Inny kolor ramki był celowy.** Seban używał `$86` zamiast `$06`, aby rozpoznawać wersję do analizy.
Rekonstrukcja ma oryginalne `$06`, żeby zachować zgodność binarną. Dawna wartość nie była błędem disassembly.

**Procedura wyszukiwania może ominąć najdłuższe dopasowanie.** Skoki kandydatów zmieniają wynik, a nie tylko czas równoważnego wyszukiwania.
[Opis wyszukiwania](SEARCH.pl.md) podaje dokładne reguły.

**SHIFT nie daje obsługi XEX.** Odrzuca sześć bajtów bez ich interpretacji.
Nie przetwarza segmentów, adresów ładowania ani wektorów RUN/INIT.

**Pytanie o zapis wybiera opakowanie.** `N` nadal zapisuje surowy plik FAST.
Oryginalny bajt `cfg_flags` nie jest inicjalizowany.
Po operacji z depackerem kolejne `N` może zachować starą flagę opakowania i dawny rozmiar.
Może wtedy powstać wadliwy XEX. Pierwsza taka decyzja też może zależeć od zastanej zawartości ZP.

**Parser liczb szesnastkowych przyjmuje interpunkcję.** Przykładowo `:;<=` daje `$3456`.
Używaj czterech cyfr szesnastkowych, mimo że parser przepuszcza inne znaki.

**Skok po depakowaniu omija zwykłe porządkowanie stosu.**
Packer zastępuje `PLA / PLA / RTS` przez `JMP adres`.
Na tej ścieżce na stosie zostają dwa adresy powrotu.
Kod, który później wykona `RTS`, musi uwzględnić ten stan.

**Żądanie odczytu nie oznacza bezpiecznej pojemności bufora.** Oryginał żąda `$9000` bajtów i oczekuje statusu EOF.
Plik dokładnie tej długości nie przechodzi oczekiwaną ścieżką EOF.
Mniejsze wejście też może wejść na dopełnienie, dane ekranu lub powiększony wynik.
Przeniesienie bufora wymaga zmian w obu przebiegach i stanie używanym wokół nich.

Zrekonstruowany kod zachowuje te właściwości, żeby wynik binarny był identyczny z oryginałem.
Polecenie Pythona ma własną walidację i nie odtwarza interaktywnego tworzenia opakowania z oryginału.

## Niezależny test historyczny: Barymag #2

Seban dostarczył cztery obrazy dyskietek. Strony A, B i C zawierają 69 plików `.P22`; strona D nie zawiera żadnego.
Pliki zajmują 293 683 bajty i dają 498 411 bajtów surowych danych.
Każdy blok ma cel `$2000` i okno od 1 do 6.

Wszystkie 69 plików rozpakowaliśmy zarówno narzędziem wiersza poleceń, jak i przez API Pythona.
Każdy wynik porównaliśmy też z trzema procedurami 6502 wykonanymi w py65:

| Procedura | Długość kodu | Porównania |
| --- | ---: | ---: |
| Oryginalny FAST, przeniesiony relokatorem packera | 204 bajty | 69 |
| Zachowany osobny depacker | 195 bajtów | 69 |
| Procedura wyciągnięta z `BARYMAG.COM` | 199 bajtów | 69 |

Wszystkie 207 porównań CPU dało te same zadeklarowane bajty wyniku.
Testy sprawdziły też wskaźnik wyjścia, przywrócenie stosu, liczbę odczytanych bajtów wejścia i bajty obok wyniku.
Model CPU używał płaskiej pamięci bez ROM-u, DMA i przerwań.
Nie był to test pełnego startu magazynu ani obsługi dysku Atari.

**Potwierdzona różnica:** procedura Barymaga dopisuje zero za zadeklarowanym wynikiem.
Potem odczytuje jeszcze jeden bajt wejścia i wraca.
Dekoder Pythona prawidłowo zwraca tylko zadeklarowane bajty.
**Prawdopodobna funkcja:** dodatkowe zero kończy tekst artykułu.
Nie prześledziliśmy całej ścieżki czytnika tekstu, więc przeznaczenie zera pozostaje wnioskiem.

Historyczne pliki potwierdzają też nadmiarową końcówkę: 56 zostawia cztery nieczytane bajty, a 13 zostawia pięć.
Obrazy magazynu i wyciągnięte artykuły są materiałem badawczym, przechowywanym poza tym repozytorium.

## Czego nadal nie wiemy?

- Dlaczego SoTe wybrał właśnie takie skoki kandydatów.
- Skąd wziął pomysł drzewa długości i czy progi dobrał eksperymentalnie.
- Ile czasu kompresji oszczędzały skoki na prawdziwym Atari.
- Jak program zachowuje się z każdym DOS-em, handlerem i wariantem ROM-u.
- Jaka jest pełna rola dodatkowego zera w Barymagu, poza zaobserwowanym zapisem.

Drzewo długości jest stałym kodem prefiksowym w formacie z rodziny LZ77/LZSS.
Ta klasyfikacja nie wskazuje, z jakiego wcześniejszego algorytmu autor mógł korzystać ani co go zainspirowało.
Program nie zawiera modelu częstości ani przesyłanego drzewa Huffmana.

## Zakres testów w repo

`tests/verify.py` sprawdza narzędzie bez katalogu badawczego.
Obejmuje historyczne sumy kontrolne, dziewięć okien, wybór trybu, błędne wejście i ochronę pliku wynikowego.
Opcjonalnie składa oba źródła i wykonuje osobny depacker w modelu 6502.

Weryfikacja pakietu 21 października 2026 przeszła na CPythonie 3.12.3 i PyPy 7.3.15 z Pythonem 3.9.18.
Osobna kopia repo przeszła wszystkie 231 prób bloków i 231 wykonań depackera w py65 1.2.0.
XASM 3.3.0 odtworzył oba historyczne pliki binarne. Polecenia z README również odtworzyły wejście bajt w bajt.
API i polecenie narzędzia z pakietu rozpakowały wszystkie 69 plików Barymaga zgodnie ze sprawdzonymi wcześniej wynikami.

Szersze wyniki historyczne i porównanie gier pochodzą z archiwum badań.
Mały zestaw testów w repo nie odtwarza całego tego zbioru.
Dalsze prace warto zacząć od przeglądu przez autora, kolejnych niezależnych plików `.P22` i testów z docelowym loaderem Atari.
