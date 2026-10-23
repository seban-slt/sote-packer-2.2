"""Match-search experiments and the optimal strategy used by sote_crunch.

No claim of Atari speed: exhaustive search and optimal parsing run on the host.
Lengths remain 2..255. Optimal encoding also supports the original depacker's
k=6..8 offset fields when enabled through sote_crunch's --extended-window.
"""
from sote_crunch import Token, historical_tokens, length_bits


def trace_historical(raw, position, k):
    """One historical search, including its zero tail; indices start at zero."""
    data = raw + bytes(512)
    assert 0 <= k <= 5 and 1 <= position < len(raw) + 256
    candidate = max(0, position - ((256 << k) - 1))
    best, distance, trace = 0, 0, []
    while candidate < position:
        candidate = data.find(data[position:position + 1], candidate, position)
        if candidate < 0:
            break
        previous_best = best
        length = 1
        while length < 256 and data[candidate + length] == data[position + length]:
            length += 1
        length = min(length, 255)
        if length == 1:
            reason, step = "second_byte_mismatch", 2
        elif length >= best:
            reason, step = "accepted", length
            best, distance = length, position - candidate
        else:
            reason, step = "shorter_than_best", length + 1
        trace.append(dict(candidate=candidate, length=length, previous_best=previous_best,
                          reason=reason, next_candidate=candidate + step))
        candidate += step
    return Token(position, best or 1, distance, data[position] if not best else 0), trace


def longest_at(raw, position, k):
    """Exhaustive candidate search, including overlapping copies.

    Start with a two-byte filter. Search newest first; a maximum possible
    match allows an early exit. Neither rule discards a better candidate.
    """
    maximum = min(255, len(raw) - position)
    if maximum < 2:
        return 0, 0
    start = max(0, position - ((256 << k) - 1))
    end, best, distance = position + 1, 0, 0
    prefix = raw[position:position + 2]
    while True:
        candidate = raw.rfind(prefix, start, end)
        if candidate < 0:
            break
        length = 2
        while length < maximum and raw[candidate + length] == raw[position + length]:
            length += 1
        if length > best:
            best, distance = length, position - candidate
            if best == maximum:
                break
        end = candidate + 1  # next two-byte match must start before candidate
    return best, distance


def match_cost(length, k):
    return 1 + len(length_bits(length)) + (8 if length >= 12 else 0) + 8 + k


def token_bits(tokens, k):
    """Bits after the six-byte fast header/first literal, before final padding."""
    return sum(match_cost(t.length, k) if t.distance else 9 for t in tokens[1:])


def trim_historical(raw, k):
    """Keep historical choices, stop at true end, shorten the last match.

    This is a comparison baseline, NOT bytewise trimming of the packed file.
    """
    tokens, _ = historical_tokens(raw, k)
    result = []
    for t in tokens:
        if t.position >= len(raw):
            break
        length = min(t.length, len(raw) - t.position)
        result.append(Token(t.position, length, t.distance) if t.distance and length >= 2
                      else Token(t.position, 1, literal=raw[t.position]))
    return result


def greedy_tokens(raw, k, matches=None):
    result, position = [Token(0, 1, literal=raw[0])], 1
    while position < len(raw):
        length, distance = matches[position] if matches is not None else longest_at(raw, position, k)
        result.append(Token(position, length, distance) if length >= 2
                      else Token(position, 1, literal=raw[position]))
        position += max(1, length)
    return result


def optimal_tokens(raw, k, matches=None):
    """Minimum bit cost for fixed k, lengths 2..255 and exact true input end.

    For each position, a longest match also supplies every shorter prefix.
    All distances cost the same for fixed k, so one distance per position
    suffices for SIZE optimization (not necessarily depacker cycle count).
    """
    n = len(raw)
    if matches is None:
        matches = [(0, 0)] + [longest_at(raw, p, k) for p in range(1, n)]
    costs, choices = [0] * (n + 1), [1] * n
    prices = [0, 9] + [match_cost(length, k) for length in range(2, 256)]
    for position in range(n - 1, 0, -1):
        costs[position] = 9 + costs[position + 1]
        maximum, _ = matches[position]
        for length in range(2, maximum + 1):
            cost = prices[length] + costs[position + length]
            if cost < costs[position]:
                costs[position], choices[position] = cost, length
    result, position = [Token(0, 1, literal=raw[0])], 1
    while position < n:
        length = choices[position]
        result.append(Token(position, length, matches[position][1]) if length >= 2
                      else Token(position, 1, literal=raw[position]))
        position += length
    return result


def encode_tokens(tokens, raw_size, k, destination=0x8000):
    """Direct FAST serialization; no historical pass-1 padding or pass 2."""
    assert tokens and tokens[0].position == 0 and tokens[0].length == 1
    assert tokens[0].distance == 0 and 0 <= k <= 8
    assert 0 < raw_size and 0 <= destination < destination + raw_size < 65536
    output = bytearray(destination.to_bytes(2, "little") + raw_size.to_bytes(2, "little")
                       + bytes([k, tokens[0].literal]))
    control, left = -1, 0

    def bits(field):
        nonlocal control, left
        for bit in field:
            if left == 0:
                control = len(output)
                output.append(0)
                left = 8
            left -= 1
            output[control] |= int(bit) << left

    position = 1
    for t in tokens[1:]:
        assert t.position == position and position + t.length <= raw_size
        if not t.distance:
            assert t.length == 1
            bits("0")
            output.append(t.literal)
        else:
            assert 2 <= t.length <= 255 and 1 <= t.distance <= min(position, (256 << k) - 1)
            bits("1" + length_bits(t.length))
            if t.length >= 12:
                output.append(t.length)
            output.append(t.distance & 255)
            if k:
                bits(f"{t.distance >> 8:0{k}b}")
        position += t.length
    assert position == raw_size
    assert len(output) == 6 + (token_bits(tokens, k) + 7) // 8
    return bytes(output)
