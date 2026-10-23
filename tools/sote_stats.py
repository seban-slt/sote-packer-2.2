"""Optional FAST-block statistics, computed after compression has finished.

No instrumentation of match search or DP. Decode only the selected block;
historical/relaxed trailing bytes and a final overlong copy are kept separate.
"""
from collections import Counter

from sote_crunch import decode, length_bits


def compression_stats(packed):
    decoded = decode(packed)
    size, k = len(decoded.data), packed[4]
    literals = sum(not token.distance for token in decoded.tokens)
    copies = [token for token in decoded.tokens if token.distance]
    count = len(copies)
    copied_bytes = sum(min(token.length, size - token.position) for token in copies)
    assert literals + copied_bytes == size

    # The first literal has no token flag. Header = destination, size, k.
    flags = len(decoded.tokens) - 1
    length_codes = sum(len(length_bits(t.length)) if t.length < 256 else 7 for t in copies)
    length_bytes = sum(t.length >= 12 for t in copies)
    control_bits = flags + length_codes + count * k
    trailing_bytes = len(packed) - decoded.consumed
    costs = dict(header=40, first_literal=8, literal_values=8 * (literals - 1),
                 token_flags=flags, length_codes=length_codes,
                 length_bytes=8 * length_bytes, offsets=count * (8 + k),
                 control_padding=(-control_bits) % 8, unread_tail=8 * trailing_bytes)
    assert sum(costs.values()) == 8 * len(packed)

    length_histogram = Counter()
    for token in copies:
        category = ("2" if token.length == 2 else "3..5" if token.length <= 5
                    else "6..8" if token.length <= 8 else "9..11" if token.length <= 11
                    else "12..255" if token.length <= 255 else "256")
        length_histogram[category] += 1
    return dict(input_bytes=size, packed_bytes=len(packed), window=k + 1,
                packed_percent=100 * len(packed) / size,
                saved_bytes=size - len(packed), bits_per_input_byte=8 * len(packed) / size,
                tokens=len(decoded.tokens), literals=literals, copies=count,
                copied_bytes=copied_bytes, copied_percent=100 * copied_bytes / size,
                average_copy_length=sum(t.length for t in copies) / count if count else 0,
                maximum_copy_length=max((t.length for t in copies), default=0),
                average_distance=sum(t.distance for t in copies) / count if count else 0,
                maximum_distance=max((t.distance for t in copies), default=0),
                overlapping_copies=sum(min(t.length, size - t.position) > t.distance for t in copies),
                final_copy_overrun=max(0, decoded.tokens[-1].position + decoded.tokens[-1].length - size),
                length_histogram=dict(length_histogram), bit_costs=costs,
                consumed_bytes=decoded.consumed, unread_tail_bytes=trailing_bytes)


def print_stats(packed):
    stats = compression_stats(packed)
    print(f"Stats (selected window {stats['window']}; decoded final block):")
    print(f"  Packed/input: {stats['packed_percent']:.2f}%; saved {stats['saved_bytes']} bytes; "
          f"{stats['bits_per_input_byte']:.3f} bits/input byte")
    print(f"  Tokens: {stats['tokens']}; literals: {stats['literals']} (includes first byte); "
          f"copies: {stats['copies']}")
    print(f"  Output covered by copies: {stats['copied_bytes']} bytes ({stats['copied_percent']:.2f}%)")
    print(f"  Copy lengths (encoded): avg {stats['average_copy_length']:.2f}, "
          f"max {stats['maximum_copy_length']}")
    print(f"  Distances: avg {stats['average_distance']:.2f}, max {stats['maximum_distance']}; "
          f"overlapping copies: {stats['overlapping_copies']}")
    print("  Length counts: " + ", ".join(
        f"{category}={stats['length_histogram'].get(category, 0)}"
        for category in ("2", "3..5", "6..8", "9..11", "12..255", "256")))
    print("  Stored bits: " + ", ".join(f"{name}={value}" for name, value in stats['bit_costs'].items()))
    print(f"  Consumed: {stats['consumed_bytes']} bytes; unread tail: {stats['unread_tail_bytes']} bytes; "
          f"final copy beyond true end: {stats['final_copy_overrun']} bytes")
