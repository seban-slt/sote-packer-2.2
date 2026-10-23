# Format danych FAST

[English](FORMAT.md) | [Strona główna](../README.pl.md)

Ten dokument opisuje końcowy blok FAST, który odczytuje i zapisuje `sote_crunch.py`.
Pozycje w tabeli liczymy w bajtach od początku bloku.

## Nagłówek

| Pozycja | Rozmiar | Znaczenie |
| ---: | ---: | --- |
| 0 | 2 | Adres docelowy, młodszy bajt pierwszy. |
| 2 | 2 | Długość wyniku, młodszy bajt pierwszy. |
| 4 | 1 | `k = okno - 1`: liczba starszych bitów odległości. |
| 5 | 1 | Pierwszy literał, bez flagi tokenu. |
| 6 | Zmienny | Bajty sterujące i bajty danych. |

Narzędzie Pythona przyjmuje `k` od 0 do 8 i niezerową długość wyniku.
Adres tuż za ostatnim bajtem wyniku, czyli wyłączny adres końca, musi być mniejszy od `0x10000`.
Oryginalny packer wybiera `k` od 0 do 5.
Oryginalne depackery odczytują też `k` od 6 do 8 bez zmiany kodu.

Token oznacza literał, czyli pojedynczy bajt, albo kopię wcześniejszych danych.
Kopia podaje dodatnią odległość wstecz i kopiuje bajty w przód.
Źródło i cel kopii mogą na siebie zachodzić.
Dzięki temu jeden literał `A` i kopia z odległości 1 tworzą długi ciąg bajtów `A`.

## Dwa odczyty, jeden wskaźnik wejścia

Dekoder ma czytnik bajtów i czytnik bitów. Oba korzystają z jednego wskaźnika wejścia.
Czytnik bitów pobiera nowy bajt sterujący dopiero po wyczerpaniu poprzedniego.
Odczytuje bity od bitu 7 do bitu 0.
Czytnik bajtów pobiera dane wprost i nie usuwa pozostałych bitów sterujących.

W bitach sterujących mieszczą się flagi tokenów, prefiksy długości i starsze bity odległości.
Literały, pełne bajty długości i młodsze bajty odległości są osobnymi bajtami danych.
Nowy bajt sterujący może wypaść w środku tokenu.
To nie jest układ: osiem flag, a za nimi osiem całych tokenów.

Pseudokod po odczytaniu nagłówka i pierwszego literału:

```text
cursor = 6
bits_left = 0

read_byte():
    require cursor < input_size
    value = input[cursor]
    cursor += 1
    return value

read_bit():
    if bits_left == 0:
        control = read_byte()
        bits_left = 8
    bits_left -= 1
    return (control >> bits_left) & 1

read_bits(count):
    value = 0
    repeat count times:
        value = (value << 1) | read_bit()
    return value
```

Pierwszy bit sterujący tokenu jest jego flagą:

- `0`: odczytaj jeden literał.
- `1`: odczytaj długość, potem odległość i wykonaj kopię.

## Kod długości

Tabela nie obejmuje flagi tokenu `1`.

| Długość | Bity sterujące | Dodatkowe dane |
| ---: | --- | --- |
| 2 | `0` | Brak |
| 3 | `100` | Brak |
| 4 | `101` | Brak |
| 5 | `110` | Brak |
| 6 | `11100` | Brak |
| 7 | `11101` | Brak |
| 8 | `11110` | Brak |
| 9 | `1111100` | Brak |
| 10 | `1111101` | Brak |
| 11 | `1111110` | Brak |
| Od 12 do 255 | `1111111` | Pełny bajt długości |

Dekoder interpretuje zero w pełnym bajcie długości jako 256.
Kompresor oryginalny i kompresor Pythona emitują długości tylko od 2 do 255.
Dekoder przyjmuje też krótsze długości zapisane pełnym bajtem.
Kompresory używają dla nich krótszych form prefiksowych.

```text
read_length():
    if read_bit() == 0:
        return 2
    base = 3
    repeat 3 times:
        pair = read_bits(2)
        if pair < 3:
            return base + pair
        base += 3
    value = read_byte()
    return 256 if value == 0 else value
```

Kodowanie długości od 2 do 255:

```text
write_length(length):
    if length == 2:
        write_bits("0")
    else if length >= 12:
        write_bits("1111111")
        write_byte(length)
    else:
        write_bits("1")
        remainder = length - 3
        while remainder >= 3:
            write_bits("11")
            remainder -= 3
        write_two_bits(remainder)
```

To stały kod prefiksowy z parami kontynuacji i wyjściem do pełnego bajtu.
Żaden pełny kod długości nie jest początkiem innego pełnego kodu długości.
Kod nie zależy od tabeli częstości zapisanej w pliku.
Strumień nie przenosi drzewa Huffmana.

## Odległość i warunek końca

Najpierw odczytaj młodszy bajt odległości, potem `k` starszych bitów, od najstarszego:

```text
low = read_byte()
high = read_bits(k)
distance = low | (high << 8)
```

Przy danym oknie każda odległość kosztuje tyle samo: `8 + k` bitów.
Odległości nie mają osobnego drzewa prefiksowego.
Przed kopią musi zachodzić `1 <= distance <= current_output_size`.

```text
length = read_length()
low = read_byte()
distance = low | (read_bits(k) << 8)
require 1 <= distance <= current_output_size
repeat min(length, declared_size - current_output_size) times:
    output.append(output[current_output_size - distance])
    current_output_size += 1
```

Depakowanie kończy się po zapisaniu zadeklarowanej liczby bajtów. W strumieniu nie ma tokenu końca.
Ostatnia kopia może deklarować więcej bajtów, niż zostało do zapisania. Depacker zatrzyma ją na zadeklarowanej długości wyniku.
Nieprzeczytane bajty za tym miejscem nie należą do wyniku.

## Zapis strumienia

Zapisuj pola sterujące i dane w tej samej kolejności, w jakiej dekoder je odczytuje.
Każdy bit sterujący wstaw w kolejną wolną pozycję bieżącego bajtu sterującego.
Gdy nie ma wolnej pozycji, dopisz zerowy bajt sterujący i zapamiętaj jego miejsce.
Bajty danych dopisuj bez zmiany liczby wolnych bitów sterujących.
Niewykorzystane bity ostatniego bajtu sterującego wypełnij zerami.
Pełna implementacja to `encode_tokens()` w [match_search.py](../tools/match_search.py).

## Koszt bitowy

Pięciobajtowy nagłówek kosztuje 40 bitów. Pierwszy literał kosztuje 8 bitów.
Każdy kolejny literał kosztuje 9 bitów: flagę i bajt danych.

| Długość kopii | Łączny koszt z flagą i odległością |
| --- | ---: |
| 2 | `10 + k` bitów |
| Od 3 do 5 | `12 + k` bitów |
| Od 6 do 8 | `14 + k` bitów |
| Od 9 do 11 | `16 + k` bitów |
| Od 12 do 255 | `24 + k` bitów |

W trybie optymalnym niech `B` oznacza sumę kosztów tokenów za pierwszym literałem.
Cały blok zajmie `6 + ceil(B / 8)` bajtów.
Tryb historyczny i tryb relaxed mogą zapisać dodatkowe bajty na końcu.

## Mały przykład

```text
00 80 08 00 00 41 F4 01
```

Ten blok daje osiem bajtów `A` pod `$8000`.
`41` to pierwszy literał. Bajt sterujący `F4` zaczyna się od `1 11101`:
flagi kopii i kodu długości 7.
Bajt odległości `01` oznacza odległość 1. Ostatnie dwa bity sterujące są niewykorzystane.

## Plik pośredni i opakowanie XEX

Oryginalny pierwszy przebieg zapisuje inny format pośredni.
Zaczyna od `k` i pierwszego literału. Wszystkie dalsze pola tworzą ciągły strumień bitów.
Nie ma w nim nagłówka z adresem docelowym i prawdziwą długością wyniku.
Wyszukiwanie obejmuje też sztuczną końcówkę zer za prawdziwymi danymi.
Drugi przebieg zmienia układ pól na FAST. Nie szuka ponownie dopasowań.
Nie podawaj pliku pośredniego dekoderowi FAST.

Dla bloku FAST długości `P` oryginalny packer może zapisać:

| Postać wyniku | Rozmiar pliku |
| --- | ---: |
| Surowy blok FAST | `P` |
| Segment XEX z blokiem FAST | `P + 6` |
| XEX z dołączonym depackerem 204-bajtowym i wektorem wejścia | `P + 216` |

Polecenie Pythona zapisuje tylko surowy FAST.
Z istniejącego pliku z opakowaniem najpierw wyodrębnij blok FAST.
