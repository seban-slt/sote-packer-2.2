#!/usr/bin/env python3
"""Encode raw bytes to SoTe Packer 2.2 FAST blocks, or decode them to raw bytes.

Default: historical two-pass encoder, window 1. --optimal minimizes the token
cost; --window auto tries all six windows and saves the smallest block.
--relaxed keeps SoTe's search and both passes, but allows larger inputs.
With --optimal or --relaxed, --extended-window enables windows 7..9
(14..16-bit distances). Relaxed auto tries all nine; optimal auto skips
extra windows that cannot add distances for the input size.
Blocks include the SoTe header, but no XEX wrapper or depacker. No third-party
dependencies; keep match_search.py alongside this file for --optimal,
and sote_stats.py for the optional --stats report after compression.
Historical input is limited to less than $9000 bytes; optimal and relaxed
input may use the 16-bit length range, with destination + size below $10000.
"""
from dataclasses import dataclass
import argparse
from pathlib import Path


@dataclass(frozen=True)
class Token:
    position: int
    length: int
    distance: int = 0
    literal: int = 0


def historical_tokens(raw: bytes, k: int, *, relaxed=False):
    """SoTe's candidate skipping and zero tail; relaxed only widens the window."""
    maximum_k = 8 if relaxed else 5
    if not 0 <= k <= maximum_k:
        raise ValueError(f"k must be 0..{maximum_k} (k=6..8 requires relaxed=True)")
    data = raw + bytes(512)
    pos, limit = 1, len(raw) + 256
    tokens = [Token(0, 1, literal=data[0])]
    window = (256 << k) - 1
    while pos < limit:
        candidate = max(0, pos - window)
        best, distance = 0, 0
        while candidate < pos:
            candidate = data.find(data[pos:pos + 1], candidate, pos)
            if candidate < 0:
                break
            if data[candidate + 1] != data[pos + 1]:
                candidate += 2  # Y=1; SEC / ADC candidate.low
                continue
            length = 2
            while length < 256 and data[candidate + length] == data[pos + length]:
                length += 1
            length = min(length, 255)  # INY wraps, DEY restores $FF
            if length >= best:
                best, distance = length, pos - candidate
                candidate += length  # DEY before SEC / ADC
            else:
                candidate += length + 1
        if best:
            tokens.append(Token(pos, best, distance))
            pos += best
        else:
            tokens.append(Token(pos, 1, literal=data[pos]))
            pos += 1
    return tokens, pos


def length_bits(length):
    if length == 2:
        return "0"
    if length < 3 or length > 255:
        raise ValueError("original encoder lengths are 2..255")
    if length >= 12:
        return "1111111"
    remainder = length - 3
    result = "1"
    while remainder >= 3:
        result += "11"
        remainder -= 3
    return result + f"{remainder:02b}"


def first_pass(raw, k, *, relaxed=False):
    tokens, processed = historical_tokens(raw, k, relaxed=relaxed)
    fields = [f"{k:08b}", f"{tokens[0].literal:08b}"]
    for token in tokens[1:]:
        if not token.distance:
            fields.extend(("0", f"{token.literal:08b}"))
        else:
            fields.extend(("1", length_bits(token.length)))
            if token.length >= 12:
                fields.append(f"{token.length:08b}")
            fields.append(f"{token.distance & 255:08b}")
            if k:
                fields.append(f"{token.distance >> 8:0{k}b}")
    bits = "".join(fields)
    bits += "0" * (-len(bits) % 8)
    packed = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    return packed, tokens, processed


class BitReader:
    def __init__(self, data, *, eof_zero=False):
        self.data, self.position, self.eof_zero = data, 0, eof_zero

    def get(self, count):
        value = 0
        for _ in range(count):
            index, bit = divmod(self.position, 8)
            if index >= len(self.data):
                if not self.eof_zero:
                    raise ValueError("truncated bit stream")
                byte = 0
            else:
                byte = self.data[index]
            value = (value << 1) | ((byte >> (7 - bit)) & 1)
            self.position += 1
        return value


def second_pass(intermediate, raw, destination=0x8000, *, relaxed=False):
    """Model $2626-$2773, including its byte-count stop and EOF zero reads.

    The original reuses the input buffer. Keep its old contents so even a
    reserved but unused final control byte is reproduced, rather than assuming
    that all padding was explicitly zeroed.

    Relaxed mode also serializes k=6..8. This generalizes the Python model,
    not the original 6502 packer's offset-alignment loop (which fails at k=8).
    """
    if not 0 <= destination <= 0xffff or len(raw) > 0xffff:
        raise ValueError("16-bit header overflow")
    size = len(intermediate) + 4
    buffer = bytearray(raw) + bytearray(max(512, size + 16 - len(raw)))
    reader = BitReader(intermediate, eof_zero=True)
    position, control, mask = 0, 0, 0x80

    class Finished(Exception):
        pass

    def byte(value):
        nonlocal position
        buffer[position] = value
        position += 1
        if position >= size:
            raise Finished

    def reserve():
        nonlocal position, control
        control = position
        position += 1

    def bits(value, count):
        nonlocal mask
        for shift in range(count - 1, -1, -1):
            if mask == 0:
                mask = 0x80
                reserve()
            buffer[control] = ((buffer[control] << 1) | ((value >> shift) & 1)) & 255
            mask >>= 1

    try:
        for value in destination.to_bytes(2, "little") + len(raw).to_bytes(2, "little"):
            byte(value)
        k = reader.get(8)
        if not 0 <= k <= (8 if relaxed else 5):
            raise ValueError("unsupported original window parameter")
        byte(k)
        byte(reader.get(8))
        reserve()
        while True:
            match = reader.get(1)
            bits(match, 1)
            if not match:
                byte(reader.get(8))
                continue
            long_length = reader.get(1)
            bits(long_length, 1)
            if long_length:
                for _ in range(3):
                    pair = reader.get(2)
                    bits(pair, 2)
                    if pair != 3:
                        break
                else:
                    byte(reader.get(8))
            byte(reader.get(8))
            if k:
                bits(reader.get(k), k)
    except Finished:
        if mask != 0x80:
            bits(0, 8)  # original flushes EIGHT bits, including beyond saved end
    return bytes(buffer[:size])


def encode(raw, k=0, destination=0x8000, *, optimal=False, extended_window=False,
           relaxed=False):
    """Encode k=0..5, or 0..8 with extended_window and optimal or relaxed.

    Optimal mode minimizes bits for lengths 2..255 and the exact input end.
    Relaxed preserves historical choices, both passes and the zero tail.
    All modes produce the same FAST format for the original depacker.
    """
    if optimal and relaxed:
        raise ValueError("optimal and relaxed are mutually exclusive")
    if extended_window and not (optimal or relaxed):
        raise ValueError("extended_window requires optimal=True or relaxed=True")
    if optimal or relaxed:
        maximum_k = 8 if extended_window else 5
        if not 0 <= k <= maximum_k:
            raise ValueError(f"k must be 0..{maximum_k}; k=6..8 requires extended_window=True")
        if not raw or not 0 <= destination < destination + len(raw) < 65536:
            raise ValueError("use nonempty input and a nonwrapping 16-bit destination")
    if optimal:
        # Imported on demand: match_search also uses this module's Token and
        # length codes, and historical encoding needs no search experiments.
        from match_search import optimal_tokens, encode_tokens
        return encode_tokens(optimal_tokens(raw, k), len(raw), k, destination)
    intermediate, _, _ = first_pass(raw, k, relaxed=relaxed)
    return second_pass(intermediate, raw, destination, relaxed=relaxed)


@dataclass(frozen=True)
class Decoded:
    data: bytes
    destination: int
    consumed: int
    tokens: tuple


def decode(packed):
    """Strict bounded decoder. Rejects empty/wrapped/invalid blocks on purpose.

    These checks are analysis-tool safety checks, NOT checks in the 6502 code.
    Length-byte zero in an extended match is accepted as 256, as on the CPU.
    k=0..8 is supported by the original depacker; its packer UI used only 0..5.
    """
    if len(packed) < 6:
        raise ValueError("header and first literal require six bytes")
    destination = int.from_bytes(packed[:2], "little")
    size = int.from_bytes(packed[2:4], "little")
    k = packed[4]
    if size == 0 or destination + size >= 65536 or k > 8:
        raise ValueError("unsupported empty/wrapping header or window")
    pos, cache, left = 6, 0, 0
    output = bytearray([packed[5]])
    tokens = [Token(0, 1, literal=packed[5])]

    def byte():
        nonlocal pos
        if pos >= len(packed):
            raise ValueError("truncated byte stream")
        value = packed[pos]
        pos += 1
        return value

    def bits(count):
        nonlocal cache, left
        value = 0
        for _ in range(count):
            if not left:
                cache, left = byte(), 8
            value = (value << 1) | (cache >> 7)
            cache = (cache << 1) & 255
            left -= 1
        return value

    while len(output) < size:
        start = len(output)
        if not bits(1):
            value = byte()
            output.append(value)
            tokens.append(Token(start, 1, literal=value))
            continue
        length = 2
        if bits(1):
            length = 3
            for _ in range(3):
                pair = bits(2)
                length += pair
                if pair < 3:
                    break
            else:
                length = byte() or 256
        distance = byte() | (bits(k) << 8)
        if not 1 <= distance <= len(output):
            raise ValueError("match points outside reconstructed history")
        tokens.append(Token(start, length, distance))
        for _ in range(min(length, size - len(output))):
            output.append(output[-distance])
    return Decoded(bytes(output), destination, pos, tuple(tokens))


def parse_xex(data):
    position = 0
    segments = []
    while position < len(data):
        while data[position:position + 2] == b"\xff\xff":
            position += 2
        if position + 4 > len(data):
            raise ValueError("truncated XEX segment header")
        start = int.from_bytes(data[position:position + 2], "little")
        end = int.from_bytes(data[position + 2:position + 4], "little")
        position += 4
        length = end - start + 1
        if length < 1 or position + length > len(data):
            raise ValueError("invalid XEX segment length")
        segments.append((start, bytes(data[position:position + length]), position))
        position += length
    return segments


def _auto_windows(raw_size, *, extended_window=False, relaxed=False):
    """Keep the six historical trials; add only useful wider offset fields.

    Relaxed also searches a synthetic tail beyond raw_size, so it tries all
    nine windows when enabled. The following pruning is for exact-end optimal.
    A copy has at least two bytes, so its latest start is raw_size - 2.
    A wider field cannot improve size if the previous field already covers
    every possible distance. Skipping it also preserves smaller-window ties.
    """
    if relaxed and extended_window:
        return list(range(1, 10))
    windows = list(range(1, 7))
    if extended_window:
        for k in range(6, 9):
            previous_limit = (256 << (k - 1)) - 1
            if raw_size - 2 > previous_limit:
                windows.append(k + 1)
    return windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("encode", "decode"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--window", choices=[str(n) for n in range(1, 10)] + ["auto"],
                        default="1", help="encode window 1..6 (7..9 with --extended-window), "
                        "or auto (default: 1)")
    strategies = parser.add_mutually_exclusive_group()
    strategies.add_argument("--optimal", action="store_true",
                            help="encode with full match search and minimum-cost token selection")
    strategies.add_argument("--relaxed", action="store_true",
                            help="keep SoTe's two-pass algorithm but allow larger inputs and windows")
    parser.add_argument("--extended-window", action="store_true",
                        help="allow windows 7..9 (16-bit distances); requires --optimal or --relaxed")
    parser.add_argument("--destination", type=lambda x: int(x, 0), default=0x8000,
                        help="depack address stored in the FAST header (default: 0x8000)")
    parser.add_argument("--stats", action="store_true",
                        help="after encode, summarize tokens and bit costs of the selected block")
    args = parser.parse_args()
    if args.stats and args.mode != "encode":
        parser.error("--stats applies only to encode")
    if args.mode == "decode" and (args.optimal or args.relaxed or args.extended_window or args.window == "auto"):
        parser.error("--optimal, --relaxed, --extended-window and --window auto apply only to encode; "
                     "decode reads the window from the block")
    if args.extended_window and not (args.optimal or args.relaxed):
        parser.error("--extended-window requires --optimal or --relaxed")
    if args.window != "auto" and int(args.window) > 6 and not args.extended_window:
        parser.error("windows 7..9 require --extended-window and either --optimal or --relaxed")
    try:
        if args.output.exists():
            raise FileExistsError(f"output already exists: {args.output}")
        raw = args.input.read_bytes()
        if args.mode == "encode":
            if not raw:
                parser.error("input is empty")
            if not (args.optimal or args.relaxed) and len(raw) >= 0x9000:
                parser.error(f"historical encoder requires input < $9000 (36864 bytes); "
                             f"got {len(raw)} bytes; use --optimal or --relaxed for larger inputs")
            if len(raw) > 0xffff:
                parser.error(f"input exceeds the 16-bit length limit (65535 bytes): {len(raw)} bytes")
            if not 0 <= args.destination <= 0xffff:
                parser.error("--destination must be a 16-bit address ($0000..$FFFF)")
            end = args.destination + len(raw)
            if end >= 0x10000:
                parser.error(f"destination ${args.destination:04X} + input size ${len(raw):04X} "
                             f"= ${end:X}; exclusive end must be below $10000")
            windows = (_auto_windows(len(raw), extended_window=args.extended_window,
                                     relaxed=args.relaxed)
                       if args.window == "auto" else [int(args.window)])
            result, selected = None, None
            for window in windows:
                candidate = encode(raw, window - 1, args.destination, optimal=args.optimal,
                                   extended_window=args.extended_window, relaxed=args.relaxed)
                if args.window == "auto":
                    print(f"window {window}: {len(candidate)} bytes", flush=True)
                # Ascending windows and strict < keep the smaller window on ties.
                if result is None or len(candidate) < len(result):
                    result, selected = candidate, window
            if args.window == "auto" and args.extended_window:
                for window in range(7, 10):
                    if window not in windows:
                        minimum_size = (256 << (window - 2)) + 2
                        print(f"window {window}: skipped (needs at least {minimum_size} input bytes)")
            strategy = "optimal" if args.optimal else "relaxed" if args.relaxed else "historical"
        else:
            result = decode(raw).data
        with args.output.open("xb") as output:
            output.write(result)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.mode == "encode":
        print(f"selected window {selected} ({strategy})")
    print(f"{len(raw)} -> {len(result)} bytes")
    if args.stats:
        from sote_stats import print_stats
        print_stats(result)


if __name__ == "__main__":
    main()
