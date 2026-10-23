#!/usr/bin/env python3
"""Verify the release without the research workspace.

Use --xasm for assembly checks. Add --cpu to execute the separate depacker
with an installed py65 package. All generated files are temporary.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sote_crunch import Token, decode, encode, parse_xex
from match_search import encode_tokens
from sote_stats import compression_stats

PACKER_HASH = "127dd1d0cb71c56a449eeeda4365e099519ed03b5c2eef75b05401e5a7f54cd4"
DEPACKER_HASH = "cee39f7651763a583eaec60a8c176fa2a770243c916d7090fa809ce668d0af5c"
# Original 6502 reference: input b"A", destination $8000, windows 1 to 6.
HISTORICAL_HASHES = (
    "c29151f679ad0a176a9d1228200e8ce41801eb6f1399f942d95b4aaa2346a46b",
    "e49b6b1651a17a8112612d9acb451baeeb679277fbc3f74211325dc3dd7303f0",
    "8a2ed101cd13d638fac349e035fdd4a40b3aca324b4caef643ca0867351f1382",
    "346bc96ede0c00627c6625db38a2fde360691b8eac1cbdc259a2ca703365df68",
    "1b7a053935c4d07f5cf7218934b663c6f5e9fe8e9d2feed06296490815672ae2",
    "8b1eb7cadeb61b8ed900e3fe9f5499b57e430961dafc879bbe88969782ff57b7",
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_blocks():
    cases = []

    def add(packed, raw):
        require(decode(packed).data == raw, "decoded data differs")
        stats = compression_stats(packed)
        require(sum(stats["bit_costs"].values()) == len(packed) * 8,
                "statistics do not account for the complete block")
        cases.append((packed, raw))

    for k, expected in enumerate(HISTORICAL_HASHES):
        require(hashlib.sha256(encode(b"A", k)).hexdigest() == expected,
                f"historical window {k + 1} differs from the CPU reference")

    fixtures = [b"A", b"A" * 600, bytes(range(256)), b"ABAC" * 79,
                bytes(range(192)) + b"ABCABC" * 31 + bytes(range(192))]
    for raw in fixtures:
        for mode in ("historical", "relaxed", "optimal"):
            for k in range(6 if mode == "historical" else 9):
                options = {} if mode == "historical" else {
                    mode: True, "extended_window": True}
                add(encode(raw, k, **options), raw)

    # Exercise every short length code and the full-byte escape in each window.
    for k in range(9):
        for length in list(range(2, 13)) + [255]:
            tokens = [Token(0, 1, literal=65), Token(1, length, 1)]
            add(encode_tokens(tokens, length + 1, k), b"A" * (length + 1))

    # Handwritten streams are independent of the encoder.
    add(bytes.fromhex("00 80 08 00 00 41 f4 01"), b"A" * 8)
    add(bytes.fromhex("00 80 01 01 00 41 ff 00 01"), b"A" * 257)

    # A genuine 16-bit distance: the final copy reaches back 32768 bytes.
    tokens = [Token(0, 1, literal=65)]
    position = 1
    while position < 32768:
        length = min(255, 32768 - position)
        tokens.append(Token(position, length, 1))
        position += length
    tokens.append(Token(position, 2, 32768))
    add(encode_tokens(tokens, 32770, 8, 0x2000), b"A" * 32770)

    invalid = [b"", bytes.fromhex("00 80 00 00 00 41"),
               bytes.fromhex("ff ff 01 00 00 41"),
               bytes.fromhex("00 80 01 00 09 41"),
               bytes.fromhex("00 80 02 00 00 41"),
               bytes.fromhex("00 80 03 00 00 41 80 00"),
               bytes.fromhex("00 80 03 00 00 41 80 02")]
    for packed in invalid:
        try:
            decode(packed)
        except ValueError:
            continue
        raise AssertionError(f"invalid block accepted: {packed.hex()}")
    return cases


def check_cli(directory):
    tool = ROOT / "tools/sote_crunch.py"

    def run(*arguments, success=True):
        result = subprocess.run([sys.executable, "-B", str(tool), *map(str, arguments)],
                                cwd=directory, capture_output=True, text=True)
        require((result.returncode == 0) == success,
                f"unexpected CLI result: {result.stdout}\n{result.stderr}")
        return result

    raw = b"ABACAB" * 19 + bytes(range(32))
    source, packed, restored = [directory / name for name in
                                ("input.bin", "output.p22", "restored.bin")]
    source.write_bytes(raw)
    result = run("encode", source, packed, "--optimal", "--window", "auto",
                 "--extended-window", "--destination", "0x2000", "--stats")
    candidates = [encode(raw, k, 0x2000, optimal=True) for k in range(6)]
    require(packed.read_bytes() == min(candidates, key=len), "auto choice differs")
    require("Stats (selected window" in result.stdout, "statistics report missing")
    run("decode", packed, restored)
    require(restored.read_bytes() == raw, "CLI round trip differs")

    original_output = packed.read_bytes()
    run("encode", source, packed, success=False)
    require(packed.read_bytes() == original_output, "existing output changed")

    rejected = directory / "rejected.p22"
    for options in [("--optimal", "--relaxed"), ("--extended-window",),
                    ("--window", "9"), ("--destination", str(65536 - len(raw)))]:
        run("encode", source, rejected, *options, success=False)
        require(not rejected.exists(), "failed encode left an output file")
    source.write_bytes(b"")
    run("encode", source, rejected, success=False)
    source.write_bytes(bytes(0x9000))
    run("encode", source, rejected, success=False)
    relaxed = directory / "relaxed.p22"
    run("encode", source, relaxed, "--relaxed", "--destination", "0x2000")
    require(decode(relaxed.read_bytes()).data == source.read_bytes(),
            "relaxed input above the historical limit differs")


def assemble(directory):
    outputs = []
    for source, name in [("src/sote_packer.xsm", "packer.xex"),
                         ("tests/depacker_at_1800.xsm", "depacker.xex")]:
        target = directory / name
        result = subprocess.run(["xasm", source, "-o", str(target)], cwd=ROOT,
                                capture_output=True, text=True)
        require(result.returncode == 0, result.stdout + result.stderr)
        outputs.append(target.read_bytes())
    require(outputs[0] == (ROOT / "bin/sote_packer.xex").read_bytes(),
            "rebuilt packer differs from the supplied binary")
    segments = parse_xex(outputs[1])
    require(len(segments) == 1 and segments[0][0] == 0x1800,
            "unexpected depacker segment")
    code = segments[0][1]
    require(len(code) == 195 and hashlib.sha256(code).hexdigest() == DEPACKER_HASH,
            "rebuilt depacker differs from the historical code")
    return code


def check_cpu(code, cases):
    from py65.devices.mpu6502 import MPU

    for packed, raw in cases:
        destination = int.from_bytes(packed[:2], "little")
        source = 0xB000 if len(raw) > 0x8000 else 0x4000
        memory = [0xA5] * 65536
        memory[0x1800:0x1800 + len(code)] = code
        memory[source:source + len(packed)] = packed
        cpu = MPU(memory=memory, pc=0x1800)
        cpu.y, cpu.x = source & 255, source >> 8
        cpu.stPushWord(0xEFFF)  # RTS returns to the stop address $F000.
        for _ in range(4_000_000):
            if cpu.pc == 0xF000:
                break
            cpu.step()
        else:
            raise AssertionError("6502 depacker did not return")
        end = destination + len(raw)
        require(bytes(memory[destination:end]) == raw, "6502 output differs")
        require(cpu.sp == 255, "6502 stack was not restored")
        require(memory[0x80] | (memory[0x81] << 8) == end, "6502 end pointer differs")
        require(memory[destination - 1] == memory[end] == 0xA5,
                "6502 write outside the declared output")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xasm", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    if args.cpu and not args.xasm:
        parser.error("--cpu requires --xasm")
    require(hashlib.sha256((ROOT / "bin/sote_packer.xex").read_bytes()).hexdigest()
            == PACKER_HASH, "supplied packer binary differs from the original")
    cases = check_blocks()
    with tempfile.TemporaryDirectory(prefix="sote-verify-") as temporary:
        directory = Path(temporary)
        check_cli(directory)
        if args.xasm:
            code = assemble(directory)
        if args.cpu:
            check_cpu(code, cases)
    print(f"PASS: {len(cases)} blocks; six historical hashes; CLI, limits and statistics")
    if args.xasm:
        print("PASS: packer and depacker assembly match the historical bytes")
    if args.cpu:
        print(f"PASS: {len(cases)} original 6502 depacker executions")


if __name__ == "__main__":
    main()
