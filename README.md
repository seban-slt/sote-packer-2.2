# SoTe Packer 2.2

[Polski](README.pl.md) | English

SoTe Packer 2.2 is a data compression program for Atari 8-bit computers.
Adam Bienias, known as SoTe / Slight, wrote the packer. Version 2.2 dates from 1994.

The packer started as a tool for our own use. Later, it became available to the demoscene free of charge.
We used version 2.2 (fast) to compress data for our demo Overmind and articles for our disk magazine, Barymag #2.
Bitter Reality used an earlier packer version with a slower depacker that read data bit by bit.

Years later, I returned to the files I had kept and the code analysis I had started long before.
I wanted to understand how the program worked, organize the sources and use the format again - this time on a modern computer too.

That work led to `sote_crunch.py`, a tool to compress and decompress data in the original format.
The original Atari depacker can decompress blocks produced by this tool.
The tool can reproduce SoTe's compression method or use a more thorough search for repeated sequences.
It can also select the optimal way to encode those sequences without changing the data format.

This repository also contains annotated packer and depacker sources, the rebuilt Atari program and an account of what we learned from the analysis.
Our compatibility tests included 69 original files from Barymag #2.

## Getting started

Use Python 3.9 or later. The tool needs only the Python standard library.
Keep all three files in `tools/` together.
Run these commands from the repository directory.

Compress a raw data file:

```sh
python3 -B tools/sote_crunch.py encode input.bin output.p22 \
  --optimal --window auto --extended-window --destination 0x2000 --stats
```

Decompress the result:

```sh
python3 -B tools/sote_crunch.py decode output.p22 restored.bin
```

Compare the input and output:

```sh
cmp input.bin restored.bin
```

Use a new output filename for each operation. The tool does not overwrite files.
The destination address plus the input size must be less than `0x10000`.

For large inputs, try `pypy3` in place of `python3`.
PyPy can substantially reduce compression time. The algorithm stays the same.
`-B` prevents Python from creating bytecode cache files. It does not enable a faster compression mode.

## Compression modes

| Option | Operation |
| --- | --- |
| No mode option | Reproduce SoTe's search and two compression passes; input must be smaller than 36,864 bytes. |
| `--relaxed` | Use the same search and two passes, with larger input and optional larger windows. |
| `--optimal` | Search all candidates and select tokens with the minimum bit cost. |
| `--window auto` | Compare block sizes and select the smallest block. |
| `--extended-window` | Permit windows 7 to 9 with `--optimal` or `--relaxed`. |
| `--stats` | Show statistics for the selected block after compression. |

Without options, the tool uses the historical mode, window 1 and destination `0x8000`.
The optimal mode minimizes size with copies of 2 to 255 bytes. The final token must end exactly at the input end.
It does not minimize decompression time.

The tool reads the complete input file as raw bytes.
It does not load XEX segments or create a self-extracting Atari program.
The `.p22` output contains a FAST header and compressed data.

## Files and documentation

| Path | Contents |
| --- | --- |
| [tools/sote_crunch.py](tools/sote_crunch.py) | Compressor and decompressor. |
| [tools/match_search.py](tools/match_search.py) | Full match search and optimal token selection. |
| [tools/sote_stats.py](tools/sote_stats.py) | Optional compression statistics. |
| [src/sote_packer.xsm](src/sote_packer.xsm) | Annotated reconstruction of the Atari packer. |
| [src/sote_depacker.xsm](src/sote_depacker.xsm) | Annotated, 195-byte depacker for XASM. |
| [bin/sote_packer.xex](bin/sote_packer.xex) | Rebuilt Atari packer. |
| [User guide](docs/USER_GUIDE.md) | Commands, limits, Atari use, build and tests. |
| [Data format](docs/FORMAT.md) | Header, control bits, lengths and distances. |
| [Match search](docs/SEARCH.md) | SoTe's search, dynamic programming and offset selection. |
| [Findings](docs/FINDINGS.md) | Program map, confirmed results and open questions. |

## Verification

The Python decoder recovered all 69 historical `.P22` files from Barymag #2.
Three original 6502 routines produced the same data in all 207 comparisons.
The [findings](docs/FINDINGS.md) describe these tests and their limits.

To run the tests that come with this repository:

```sh
python3 -B tests/verify.py
```

## Credits and license

Original packer, data format and depacker: Adam Bienias (SoTe / Slight).
The original program credits him as Soused Teat / Slight.

Material preservation, historical disassembly and project work:
Seban / Slight. Further analysis, source reconstruction, documentation
and Python tools were developed with help from Codex (GPT-6 Astra model).

The original program and its source code are shared with permission
from Adam Bienias.

The code and documentation in this repository are available under
the MIT License. See [LICENSE](LICENSE) for the full terms.
