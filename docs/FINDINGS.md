# Findings and evidence

[Polski](FINDINGS.pl.md) | [Home](../README.md)

The analysis draws on the original XEX, preserved depacker source, historical disassembly and results from execution tests.
Comments and labels are explanations of that evidence. They are not original author symbols unless stated otherwise.

## Program map

The original XEX loads a run vector at `$02E0`, data at `$0480` to `$06FB`, and code at `$2000` to `$2A67`.
The fixed data buffer starts at `$2B00`.

| Part | Function |
| --- | --- |
| Startup and screen routines | Set up the editor, messages and compression progress display. |
| CIO helpers | Open, read, write and close files; show a directory or return to DOS. |
| Input preparation | Read raw bytes at `$2B00`, optionally discard six bytes, then append 512 zeros. |
| Window selection | Convert the user's choice 1 to 6 into `k=0..5`. |
| `pack_loop` and match search | Search the earlier input with candidate skips and choose a copy or literal. |
| First-pass bit writer | Write the selected tokens as a continuous bit stream to the output file. |
| `finish_1st_pass`, `save_as_file` | Select raw FAST or XEX, memory addresses, depacker and final jump. |
| `second_pass` | Read the intermediate file and rearrange fields into FAST in the data buffer. |
| Embedded depacker | Restore bytes from the FAST stream; 204 bytes when appended to an output file. |
| Relocation and final save | Adjust the appended depacker's addresses, write the selected wrapper and vector. |

Zero-page storage has several roles over time.
The annotated source groups aliases by phase and gives each alias its physical address.
An `EQU` does not allocate another variable or preserve its previous value.
The `(variable reused)` comments identify shared storage, including partially overlapping words.

## Confirmed results

- The reconstructed packer produces the original 3,316-byte XEX exactly.
- The historical Python encoder matched both passes of the original packer in 66 trials: 11 inputs and six windows.
- The separate depacker source produces 195 bytes, identical to the preserved routine at `$1800`.
- Original depackers decode extended distance fields through 16 bits. The original interface offers only 8 to 13 bits.
- FAST has one flag bit per literal after the first. It has fixed length codes and fixed-width distances.
- The second pass changes field placement. It does not perform another match search.
- The original input buffer is fixed. The packer does not choose it from `MEMLO`.

These facts support the source comments about the two passes, bit readers, length tree, distance fields and relocation.
We do not know the exact form of the original source or the author's variable names.

SHA-256 of both the original XEX and the rebuilt `bin/sote_packer.xex`:

```text
127dd1d0cb71c56a449eeeda4365e099519ed03b5c2eef75b05401e5a7f54cd4
```

SHA-256 of the 195 code bytes from the separate depacker, assembled at `$1800`:

```text
cee39f7651763a583eaec60a8c176fa2a770243c916d7090fa809ce668d0af5c
```

## Corrected interpretations and retained bugs

**The border-color difference was deliberate.** Seban used `$86` instead of `$06` to identify his analysis build.
The reconstruction uses the original `$06` for binary identity. The old value was not a disassembly mistake.

**The search can miss the longest match.** Candidate skips are real behavior, not just faster equivalent search.
The [search document](SEARCH.md) gives the exact rules.

**SHIFT does not implement XEX support.** It discards six bytes without interpreting them.
It does not process segments, load addresses, or RUN/INIT vectors.

**The save question selects a wrapper.** `N` still saves a raw FAST file.
The original `cfg_flags` byte has no initialization.
After an operation with a depacker, a subsequent `N` can retain a stale wrapper flag and old size.
This can produce a malformed XEX. The first such decision can also depend on previous zero-page contents.

**The hexadecimal parser accepts punctuation.** For example, `:;<=` becomes `$3456`.
Use four hexadecimal digits even though the parser accepts more characters.

**A post-depack jump does not perform the normal stack cleanup.**
The packer replaces `PLA / PLA / RTS` with `JMP address`.
Two return addresses remain on the stack on that path.
A target that later uses `RTS` must account for this state.

**The read request is not a safe buffer capacity.** The original requests `$9000` bytes and expects EOF status.
A file of exactly that size does not take the expected EOF path.
Smaller input can still collide with padding, display data or expanded output.
Moving the buffer requires changes in both passes and their surrounding state.

The source preserves these behaviors to keep the binary identical.
The Python command has its own validation and does not implement the original interactive file wrapper.

## Independent historical test: Barymag #2

Seban supplied all four disk images. Sides A, B and C contain 69 `.P22` files; side D contains none.
The files contain 293,683 packed bytes and produce 498,411 raw bytes.
Every block has destination `$2000` and a window from 1 to 6.

We decoded all 69 files with both the Python command-line tool and its API.
Each result also matched three 6502 routines executed with py65:

| Routine | Code size | Comparisons |
| --- | ---: | ---: |
| Original FAST routine, relocated by the packer's own code | 204 bytes | 69 |
| Preserved separate depacker | 195 bytes | 69 |
| Routine extracted from `BARYMAG.COM` | 199 bytes | 69 |

All 207 CPU comparisons agreed on the declared output bytes.
The tests also checked the output pointer, stack restoration, number of input bytes read and bytes next to the output.
The CPU model used flat memory without ROM, DMA or interrupts.
The tests did not start the complete magazine program or use Atari disk access.

**Confirmed difference:** the Barymag routine writes an additional zero after the declared output.
It then reads one extra input byte before return.
The Python decoder correctly returns only the declared bytes.
**Likely purpose:** the additional zero terminates article text.
The complete text-reader path was not traced, so that purpose remains an inference.

The historical files also confirm unused tail data: 56 leave four unread bytes; 13 leave five.
The magazine images and extracted articles are research material, separate from this repository.

## What is still unknown?

- SoTe's reason for the particular candidate skips.
- The source of the length-tree idea and whether tests determined its thresholds.
- Compression-time gains from the skips on an actual Atari.
- Compatibility with every DOS, handler and OS ROM revision.
- The full purpose of the Barymag variant's additional zero, beyond the observed write.

The length tree is a fixed prefix code in an LZ77/LZSS-style format.
That classification does not establish a specific named predecessor or the author's inspiration.
The program contains no frequency model or transmitted Huffman tree.

## Scope of the release tests

`tests/verify.py` checks the tool without the research workspace.
It covers historical reference hashes, all nine windows, mode selection, malformed input and output-file protection.
Optional checks rebuild both sources and execute the separate depacker on a 6502 model.

Release verification on 21 October 2026 passed with CPython 3.12.3 and PyPy 7.3.15, which implements Python 3.9.18.
The isolated repository copy passed all 231 block tests and all 231 depacker executions with py65 1.2.0.
XASM 3.3.0 reproduced both historical binaries. The README commands also restored their test input exactly.
The release tool's API and command decoded all 69 Barymag files to the previously verified outputs.

The broader historical and game results above come from the research archive.
The compact release tests do not reproduce that entire corpus.
For further work, prioritize author review, additional independent `.P22` files and tests in the intended Atari loader.
