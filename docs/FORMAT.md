# FAST data format

[Polski](FORMAT.pl.md) | [Home](../README.md)

This document describes the final FAST block that `sote_crunch.py` reads and writes.
All positions below are byte offsets from the start of that block.

## Header

| Offset | Size | Meaning |
| ---: | ---: | --- |
| 0 | 2 | Destination address, low byte first. |
| 2 | 2 | Output size, low byte first. |
| 4 | 1 | `k = window - 1`: number of high distance bits. |
| 5 | 1 | First literal byte, without a token flag. |
| 6 | Variable | Control bytes and payload bytes. |

The Python tool accepts `k` from 0 to 8 and nonzero output sizes.
The exclusive end address, immediately after the last output byte, must be below `0x10000`.
The original packer selects `k` from 0 to 5.
The original depackers also decode `k` from 6 to 8 without a code change.

A token is either a literal byte or a copy from earlier output.
A copy uses a positive backward distance and proceeds forwards.
The source and destination of a copy can overlap.
Thus, one literal `A` and a copy at distance 1 can produce a long run of `A` bytes.

## Two read operations, one input pointer

The decoder has a byte reader and a bit reader. They share one input pointer.
The bit reader fetches a new control byte only when it has no bits left.
It reads control bits from bit 7 to bit 0.
The byte reader fetches payload directly and leaves cached control bits unchanged.

Control bits contain token flags, length prefixes and high distance bits.
Payload bytes contain literals, full length bytes and low distance bytes.
A new control byte can occur inside a token.
Do not parse the stream as eight flags followed by eight complete tokens.

Pseudocode, after the header and first literal:

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

The first control bit of a token is its flag:

- `0`: read one literal byte.
- `1`: decode a length, then read a distance and copy data.

## Length code

The table excludes the token flag `1`.

| Length | Control bits | Extra payload |
| ---: | --- | --- |
| 2 | `0` | None |
| 3 | `100` | None |
| 4 | `101` | None |
| 5 | `110` | None |
| 6 | `11100` | None |
| 7 | `11101` | None |
| 8 | `11110` | None |
| 9 | `1111100` | None |
| 10 | `1111101` | None |
| 11 | `1111110` | None |
| 12 to 255 | `1111111` | One full length byte |

The decoder interprets a full length byte of zero as 256.
The original and Python encoders emit lengths only from 2 to 255.
The decoder can also accept shorter lengths through the full-byte escape.
The encoders use the shorter prefix forms for those lengths.

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

To encode a length from 2 to 255:

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

This is a fixed prefix code with continuation pairs and a full-byte escape.
No complete length code is a prefix of another complete length code.
The code does not depend on a frequency table in the file.
There is no transmitted Huffman tree.

## Distance and end condition

Read the low distance byte first. Then read `k` high bits, most significant bit first:

```text
low = read_byte()
high = read_bits(k)
distance = low | (high << 8)
```

For a fixed window, every distance costs the same `8 + k` bits.
There is no separate prefix tree for distances.
Require `1 <= distance <= current_output_size` before a copy.

```text
length = read_length()
low = read_byte()
distance = low | (read_bits(k) << 8)
require 1 <= distance <= current_output_size
repeat min(length, declared_size - current_output_size) times:
    output.append(output[current_output_size - distance])
    current_output_size += 1
```

Decompression stops when the output reaches the declared size. The stream has no end token.
The last copy can state more bytes than remain. The depacker stops at the declared size.
Bytes that remain unread after that point do not belong to the output.

## Write operations

The writer uses the same order of control and payload fields as the reader.
For each control bit, put that bit into the next free position of the current control byte.
If no position is free, append a zero control byte and remember its location.
Payload writes append a byte without changing the free control-bit count.
Use zero for unused bits in the final control byte.
See `encode_tokens()` in [match_search.py](../tools/match_search.py) for the complete implementation.

## Bit costs

The five-byte header costs 40 bits. The first literal costs 8 bits.
Every subsequent literal costs 9 bits: one flag and one byte.

| Copy length | Total cost, including flag and distance |
| --- | ---: |
| 2 | `10 + k` bits |
| 3 to 5 | `12 + k` bits |
| 6 to 8 | `14 + k` bits |
| 9 to 11 | `16 + k` bits |
| 12 to 255 | `24 + k` bits |

For optimal mode, let `B` be the total token cost after the first literal.
The complete block size is `6 + ceil(B / 8)` bytes.
Historical and relaxed modes can store additional bytes at the end.

## Small example

```text
00 80 08 00 00 41 F4 01
```

This block produces eight `A` bytes at `$8000`.
`41` is the first literal. Control byte `F4` starts with `1 11101`:
the copy flag and the length code for 7.
Distance byte `01` selects distance 1. The last two control bits are unused.

## Intermediate file and XEX wrapper

The original first pass writes a different intermediate format.
It starts with `k` and the first literal. All later fields share one continuous bit stream.
It has no destination or true output-size header.
The search continues into a synthetic zero tail beyond the real input.
The second pass changes the field layout to FAST. It does not search for matches again.
Do not use the intermediate file as input to the FAST decoder.

For a FAST block of `P` bytes, the original packer can save:

| Output form | File size |
| --- | ---: |
| Raw FAST block | `P` |
| XEX segment containing FAST | `P + 6` |
| XEX with appended 204-byte depacker and entry vector | `P + 216` |

The Python command writes the raw FAST form only.
For an existing wrapped file, extract its FAST block before decoding.
