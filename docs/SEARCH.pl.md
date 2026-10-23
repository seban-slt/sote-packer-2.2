# Wyszukiwanie dopasowań i wybór optymalny

[English](SEARCH.md) | [Strona główna](../README.pl.md)

Format danych nie narzuca algorytmu wyszukiwania.
Inny kompresor może wybrać inne kopie i nadal korzystać z oryginalnego depackera.
Ten projekt udostępnia algorytm historyczny i wariant optymalny.

## Jak SoTe wyszukuje dopasowania

Na każdej pozycji wejścia procedura wyszukiwania zaczyna od najstarszego kandydata w wybranym oknie.
Znajduje kandydata z takim samym pierwszym bajtem, potem porównuje kolejne bajty.
Może porównać 256 bajtów, ale długość zapisywanej kopii ogranicza do 255.

Pozycja następnego kandydata zależy od wyniku:

| Wynik | Następna pozycja kandydata |
| --- | --- |
| Drugi bajt jest inny | Bieżący kandydat plus 2. |
| Dopasowanie jest co najmniej tak długie jak dotychczas najlepsze | Bieżący kandydat plus długość dopasowania. |
| Dopasowanie jest krótsze od dotychczas najlepszego | Bieżący kandydat plus długość dopasowania plus 1. |

Przy równej długości nowe dopasowanie zastępuje poprzednie.
Wśród faktycznie odwiedzonych kandydatów remis wygrywa więc nowszy.
Skoki mogą jednak ominąć dłuższe lub bliższe dopasowanie.
Procedura nie gwarantuje znalezienia najdłuższej kopii w oknie.
Model Pythona zachowuje te skoki i reguły remisów.

Po wyborze kompresor przesuwa pozycję wejścia o długość kopii albo jeden bajt literału.
Nie porównuje kosztu tego wyboru z wyborami, które pojawią się później.
To reguła zachłanna.

Oryginał dopisuje za wejściem 512 zerowych bajtów.
Nowe tokeny mogą zaczynać się również w pierwszych 256 bajtach tej zerowej końcówki.
Ostatnia kopia może sięgnąć dalej.
Rzeczywista długość danych zapisana w nagłówku FAST nadal zatrzymuje depakowanie na właściwym bajcie.
Tryb historyczny i tryb relaxed zachowują tę końcówkę i oba przebiegi kompresji.

`--relaxed` zmienia ograniczenia długości i okna w modelu Pythona.
Nie odpowiada oryginalnemu packerowi z samymi zdjętymi limitami.
Przykładowo oryginalna pętla wyrównania w drugim przebiegu wymaga zmian dla `k=8`.

## Co robi tryb optymalny

Na każdej pozycji `longest_at()` znajduje najdłuższe dozwolone dopasowanie, również z nakładaniem się kopii.
Sprawdza kandydatów od najnowszego do najstarszego, z filtrem dwóch początkowych bajtów.
Kończy wcześniej tylko wtedy, gdy dopasowanie osiągnie maksymalną możliwą długość.
Żadna z tych reguł nie usuwa kandydata, który mógłby poprawić najdłuższe dopasowanie.

Następny etap dobiera cały ciąg tokenów przez programowanie dynamiczne, czyli DP.
Tutaj DP oznacza: policz koszt każdej pozostałej końcówki danych i korzystaj z gotowego wyniku.
To metoda planowania kolejnych decyzji, gdy każda zmienia sytuację dla następnych.

Niech `cost[p]` oznacza najmniejszą liczbę bitów potrzebną od pozycji `p` do końca wejścia.
`price(L, k)` to koszt kopii z [tabeli formatu](FORMAT.pl.md).
Pierwszy literał jest obowiązkowy, więc zależność liczymy od pozycji 1.

```text
cost[n] = 0
for p from n-1 down to 1:
    cost[p] = 9 + cost[p+1]
    choice[p] = literal
    for L from 2 to longest_match[p]:
        candidate_cost = price(L, k) + cost[p+L]
        if candidate_cost < cost[p]:
            cost[p] = candidate_cost
            choice[p] = copy of L bytes
```

Po obliczeniu tabeli odczytujemy zapisane decyzje od pozycji 1 do końca.
Krótsza kopia może wygrać, jeśli zostawia lepszy początek następnego tokenu.
Przy równym koszcie implementacja zachowuje literał.
Spośród kopii o równym koszcie zachowuje krótszą, bo sprawdza długości rosnąco.

Wybrane tokeny kończą się dokładnie na końcu prawdziwych danych.
Zapis tworzy FAST bezpośrednio, bez historycznego pliku pośredniego i sztucznej końcówki.

## Który offset wybiera DP?

Przy stałym `k` wszystkie odległości kosztują `8 + k` bitów.
Każdy krótszy początek najdłuższego dopasowania również jest poprawnym dopasowaniem.
Dlatego do optymalizacji rozmiaru wystarczy jedno najdłuższe dopasowanie z jego odległością na każdej pozycji.
DP może wybrać krótszy początek i zachować odległość tego najdłuższego dopasowania.

Spośród najdłuższych dopasowań o równej długości procedura wyszukiwania zachowuje najbliższe.
Dla krótszego wybranego początku ta odległość nie musi być najbliższą możliwą.
Nie zmienia to rozmiaru zapisu.
Może zmienić czas depakowania, którego to DP nie optymalizuje.

## Co tutaj znaczy optymalny?

Dla stałego okna wynik ma najmniejszy koszt bitowy przy takich zasadach:

- Pierwszy bajt wyniku jest literałem bez flagi.
- Długość kopii wynosi od 2 do 255.
- Kopie korzystają z poprawnej historii, także z nakładaniem się źródła i celu.
- Ostatni token kończy się dokładnie na końcu wejścia.
- Tokeny używają zwykłych kodów długości z tabeli formatu.

Rozmiar zapisu wynosi `6 + ceil(token_bits / 8)`, więc najmniejszy koszt bitowy daje też najmniej bajtów w tym modelu.
Kilka ciągów tokenów może dać taki sam rozmiar bajtowy.
Twierdzenie nie obejmuje kopii długości 256 ani ostatniej kopii wychodzącej za prawdziwy koniec.
Dekoder je przyjmuje, ale ten enkoder optymalny ich nie rozważa.

## Wybór okna to osobna decyzja

`--optimal --window 4` znajduje najlepszy ciąg tokenów dla okna 4.
`--optimal --window auto` powtarza to dla potrzebnych okien i porównuje rozmiary bloków.
Dodanie `--extended-window` uwzględnia użyteczne okna większe od 6.

Szersze okno pozwala znaleźć dalsze powtórzenia, ale podnosi koszt każdej kopii.
Może więc dać większy blok, nawet przy optymalnym doborze tokenów.
Automatyczny wybór obejmuje też mniejsze okna i zachowuje najmniejszy wynik.

## Co pokazał test gier

W badaniu użyliśmy 21 całych plików jako surowych danych, razem z nagłówkami XEX tam, gdzie występowały.
Porównaliśmy historyczny algorytm wyszukiwania z trybem optymalnym.
Dla danych powyżej oryginalnego limitu bazą historyczną był tryb relaxed.

Najlepsze historyczne okna od 1 do 6 dały razem 328 249 bajtów.
Optymalne okna od 1 do 9 dały 320 749 bajtów: o 7500 mniej, czyli 2,28%.
Okna 3 i 4 wygrały w 15 z 21 prób optymalnych.
Okno 7 wygrało raz. Okna 8 i 9 nie wygrały ani razu.

Na różnicę 7500 bajtów złożyły się kolejne zmiany:

| Zmiana | Zaoszczędzone bajty |
| --- | ---: |
| Dokładny koniec danych i bezpośredni zapis FAST | 125 |
| Pełne wyszukiwanie, nadal z zachłannym wyborem najdłuższej kopii | 2561 |
| DP przy tym samym oknie | 3878 |
| Ponowny wybór okna od 1 do 6 | 573 |
| Dopuszczenie okien od 7 do 9 | 363 |

Te oszczędności zależą od danych testowych i kolejności zmian. Nie dotyczą każdego możliwego wejścia.
Dekoder Pythona odtworzył wejście ze wszystkich 756 wygenerowanych bloków.
W tym teście gier nie wykonaliśmy każdego bloku na 6502.

**Potwierdzone:** pomijanie kandydatów kosztowało w tym zbiorze niewiele dodatkowego miejsca.
**Wniosek:** dla tych plików oryginalny algorytm wyszukiwania zostawiał niewiele miejsca na dalsze zmniejszenie wyniku.
**Niewiadome:** czy SoTe pomijał kandydatów świadomie i ile czasu Atari dzięki temu oszczędzało.
Test nie dowodzi intencji autora ani zachowania dla wszystkich rodzajów danych.
