# User guide

[Polski](USER_GUIDE.pl.md) | [Home](../README.md)

## Python tool

Run commands from the repository directory. Keep the three Python modules in `tools/` together.
They need no external packages. We tested the tool with Python 3.9 and 3.12.

To select the smallest block with optimal mode, use:

```sh
python3 -B tools/sote_crunch.py encode input.bin output.p22 \
  --optimal --window auto --extended-window --destination 0x2000
```

Optimal mode uses the rules described in [Match search](SEARCH.md).
The tool compresses once for each applicable window, then compares the complete block sizes.
If two sizes are equal, it selects the smaller window.
Optimal mode omits extended windows that cannot add usable distances for the input size.

To reproduce the historical algorithm with window 3, use:

```sh
python3 -B tools/sote_crunch.py encode input.bin historical.p22 \
  --window 3 --destination 0x2000
```

To keep that algorithm with larger input or windows, use:

```sh
python3 -B tools/sote_crunch.py encode input.bin relaxed.p22 \
  --relaxed --window auto --extended-window --destination 0x2000
```

Do not combine `--optimal` and `--relaxed`.
`--extended-window` requires one of these modes.
Without `--extended-window`, automatic selection uses windows 1 to 6.
Relaxed mode with extended windows tries all nine windows, including its synthetic zero tail.

For decompression, the header supplies the window, output size and destination:

```sh
python3 -B tools/sote_crunch.py decode input.p22 output.bin
```

The decoder writes only the raw data. It does not insert padding before the stored destination address.
It stops at the declared output size and permits unread bytes after the compressed stream.
It rejects truncated data, invalid history references and unsupported header values.
The original 6502 routine has no equivalent input checks.

## Limits and addresses

The command-line tool requires nonempty input.
Historical mode accepts fewer than `0x9000` bytes. Optimal and relaxed modes accept up to 65,535 bytes.
All modes require:

```text
0 <= destination < destination + input_size < 65536
```

An end address equal to `0x10000` is also invalid.
The original depacker's end test does not support that case.
The default destination is `0x8000`, which limits input to 32,767 bytes.
For 44,026 bytes at `0x1006`, use `--optimal` or `--relaxed` and set `--destination 0x1006`.

The destination is a header field. It does not reserve Atari memory.
Before use on Atari, select memory areas for the compressed data, output, code, zero page and stack.
For your first tests on Atari, keep these areas separate and use writable RAM.

| Window | Distance bits | Maximum backward distance |
| ---: | ---: | ---: |
| 1 | 8 | 255 |
| 2 | 9 | 511 |
| 3 | 10 | 1,023 |
| 4 | 11 | 2,047 |
| 5 | 12 | 4,095 |
| 6 | 13 | 8,191 |
| 7 | 14 | 16,383 |
| 8 | 15 | 32,767 |
| 9 | 16 | 65,535 |

Each distance must also fit in the data already decompressed.
The original interface exposes only windows 1 to 6. The original depackers can read all nine.

## Speed and statistics

To use PyPy, replace `python3` with `pypy3` in a command.
PyPy's JIT compiler can make these Python loops much faster.
The benefit depends on the data and the selected window.
The project keeps a direct, readable algorithm. It has no hash-table search or parallel compression.

Append `--stats` to an encode command to show token counts, copy lengths, distances and bit costs.
The report also shows overlapping copies, unread bytes at the end and any part of the final copy beyond the output size.
It reads the selected compressed block once after compression. It does not repeat the search or dynamic programming.
Without `--stats`, the tool does not calculate this report.

## Using the separate depacker

Include [sote_depacker.xsm](../src/sote_depacker.xsm) after your chosen `ORG`.
The file defines `depack` and its helper labels. It uses zero-page bytes `$80` to `$85`.
Change the four `EQU` values if your program reserves different zero-page locations.
Each pointer needs two consecutive bytes.

Call the routine as follows:

```asm
; packed_data points to the FAST header in RAM.

			cld
			ldy	<packed_data
			ldx	>packed_data
			jsr	depack
```

The routine changes A, X, Y, flags, its zero-page variables and its own instruction operands.
It writes each output byte to `COLBK` as well as the output buffer.
Keep the code in RAM at its assembled address. Do not relocate its bytes without updating absolute addresses.
After the final output byte, the routine returns to the instruction after `JSR depack`.
The header supplies the destination. The call supplies only the compressed-data address.

This source produces 195 bytes. The original packer appends a different, 204-byte routine and has its own relocator.

## Building and testing

Install XASM separately if you want to assemble the Atari sources.
The included binary needs no assembler at run time.
Assembly files use hard tabs with a width of 8.
The editor settings keep the label, opcode, operand and comment columns aligned.

```sh
mkdir -p build
xasm src/sote_packer.xsm -o build/sote_packer.xex
cmp bin/sote_packer.xex build/sote_packer.xex
xasm tests/depacker_at_1800.xsm -o build/sote_depacker.xex
```

The last command creates a test segment at `$1800`. It does not create a standalone Atari program.
XASM resolves its include path from the repository directory.

Run the tests included in this repository:

```sh
python3 -B tests/verify.py
```

Add assembly and binary checks:

```sh
python3 -B tests/verify.py --xasm
```

If your interpreter has the optional `py65` package, also execute the 6502 depacker:

```sh
python3 -B tests/verify.py --xasm --cpu
```

The CPU test uses flat memory without Atari ROM, interrupts or DMA.
It does not test DOS, the screen or disk access.
The script uses temporary files and removes them after the test.

## Using the original Atari packer

Load `bin/sote_packer.xex` with an Atari binary loader.
The program uses internal XL/XE ROM routines as well as CIO.
The reconstruction preserves these dependencies and the original bugs.

1. Enter the input filename. The prompts also offer `*` for a directory and `#` for DOS.
2. To discard the first six input bytes, hold SHIFT when the program opens the input.
3. Enter the output filename and select window 1 to 6.
4. Wait for the first pass. It writes an intermediate file under the output filename.
5. Answer the output questions. The second pass replaces the intermediate file with the final result.

SHIFT only discards six bytes. It does not parse a XEX header or load multiple segments.
Select an output filename different from your input filename.

| Original prompt | Meaning |
| --- | --- |
| `Save this as a file ?` | Select XEX wrapping. `N` requests a raw FAST block; it does not cancel the save. |
| `Depack adress.` | Set the destination for decompressed bytes. |
| `Adress of file location.` | Set the load address of the compressed block. |
| `Include depacker ?` | Append the 204-byte depacker. |
| `Adress to run.` | Select where to store the depacker entry vector; the default is `INITAD`, `$02E2`. |
| `Run after depack ?` / `Where to jump ?` | Replace the normal return with a jump to the selected address. |

Enter addresses as four hexadecimal characters, `0` to `9` or `A` to `F`.
The address parser also accepts some punctuation by mistake.
The save flags can retain state from a previous operation and produce a malformed file.
See [confirmed bugs](FINDINGS.md) before relying on repeated saves or post-depack jumps.

The fixed input buffer starts at `$2B00`. The read request is `0x9000` bytes.
This request is not a guarantee that all smaller inputs fit safely in Atari memory.
The program also needs padding, output space and display memory.
Use the Python tool for large raw blocks.
