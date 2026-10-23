# Match search and optimal selection

[Polski](SEARCH.pl.md) | [Home](../README.md)

The compressed format does not require a particular search algorithm.
A different compressor can choose different copies and still use the original depacker.
This project provides the historical algorithm and an optimal alternative.

## How SoTe searches for matches

At each input position, the search starts with the oldest candidate in the selected window.
It finds a candidate with the same first byte, then compares subsequent bytes.
It can compare 256 bytes, but limits the emitted copy to 255 bytes.

The next candidate depends on the result:

| Result | Next candidate position |
| --- | --- |
| Second byte differs | Current candidate plus 2. |
| Match length is at least the current best | Current candidate plus match length. |
| Match is shorter than the current best | Current candidate plus match length plus 1. |

An equal-length match replaces the previous choice.
Among the candidates actually visited, this favors a more recent match on a tie.
However, the jumps can skip a longer match or a nearer match.
The routine does not guarantee the longest match in the window.
The Python model preserves these jumps and tie rules.

After the choice, the compressor advances by the selected copy length or one literal byte.
It does not compare the cost of this choice with the choices that follow.
This is a greedy selection rule.

The original prepares 512 zero bytes after the input.
It permits new tokens to start before the true end plus 256.
A final copy can extend further.
The true output size in the FAST header still ends decompression at the correct byte.
Historical and relaxed modes retain this tail and both compression passes.

`--relaxed` changes the Python model's size and window limits.
It does not represent an original packer version with those limits removed.
For example, the original second-pass alignment loop does not work for `k=8` without changes.

## What optimal mode does

For each position, `longest_at()` finds a longest legal match, including overlap.
It searches candidates from newest to oldest, with a two-byte filter.
It stops early only if a match reaches the maximum possible length.
Neither rule removes a candidate that could improve the maximum length.

The next stage selects the complete token sequence by dynamic programming, or DP.
Here, DP calculates the minimum cost from each position to the input end, then reuses those results.
It is a method for a sequence of dependent decisions.

Let `cost[p]` be the minimum number of bits needed from position `p` to the input end.
Let `price(L, k)` be the copy cost from the [format table](FORMAT.md).
The first literal is compulsory, so the recurrence starts at position 1.

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

After this calculation, follow the saved choices from position 1 to the end.
A shorter copy can win because it leaves a better starting position for the next token.
If a literal and a copy have the same total cost, the implementation keeps the literal.
Between equal-cost copies, it keeps the shorter length because it tests lengths in ascending order.

The selected tokens end exactly at the true input end.
The writer creates FAST directly, without the historical intermediate file or synthetic tail.

## Which offset does DP select?

For a fixed `k`, all distances cost `8 + k` bits.
A longest match also supplies every shorter prefix of that match.
Thus, one longest match and its distance are sufficient at each position for size optimization.
DP can select a shorter prefix and retain that longest match's distance.

The search retains the nearest candidate among equal longest matches.
For a shorter selected prefix, that distance need not be the nearest possible distance.
This does not change its encoded size.
It can change decompression timing, which this DP does not optimize.

## What does optimal mean here?

For a fixed window, the result has minimum token bit cost under these rules:

- The first output byte is a literal without a flag.
- Copy lengths range from 2 to 255.
- Copies use valid earlier output, including overlap.
- The last token ends exactly at the input end.
- Tokens use the normal length codes in the format table.

The stored size is `6 + ceil(token_bits / 8)`, so minimum bit cost also minimizes bytes within this model.
Several token sequences can produce the same byte size.
The claim does not cover 256-byte copies or a final copy that extends beyond the true end.
The decoder accepts those cases, but this optimal encoder does not search them.

## Window selection is a separate decision

`--optimal --window 4` finds the best token sequence for window 4.
`--optimal --window auto` repeats that operation for each applicable window and compares block sizes.
Add `--extended-window` to include useful windows above 6.

A wider window finds more distant matches but charges more bits for every copy.
It can therefore produce a larger block, even with optimal token selection.
Automatic selection includes the smaller windows and keeps the smallest result.

## What the game test showed

The research test used 21 complete files as raw bytes, including XEX headers where present.
It compared the historical search with the optimal mode.
For inputs above the original limit, the historical baseline used relaxed mode.

The best historical windows 1 to 6 produced 328,249 bytes in total.
Optimal windows 1 to 9 produced 320,749 bytes: 7,500 fewer bytes, or 2.28%.
Windows 3 and 4 won 15 of the 21 optimal trials.
Window 7 won once. Windows 8 and 9 did not win.

The following sequential changes account for that 7,500-byte difference:

| Change | Bytes saved |
| --- | ---: |
| End exactly at the input end and write FAST directly | 125 |
| Use full search, still with greedy longest-copy selection | 2,561 |
| Use DP at the same window | 3,878 |
| Select the window again from 1 to 6 | 573 |
| Permit windows 7 to 9 | 363 |

These savings depend on the test data and the order of the changes. They do not apply to every input.
The Python decoder restored the original input from all 756 generated blocks.
This game test did not execute every block on a 6502.

**Confirmed:** skipping candidates caused only a small size loss in this corpus.
**Inference:** the original search left little room for further size reduction on these files.
**Unknown:** whether SoTe chose the skips deliberately, and how much Atari time they saved.
The test does not establish the author's intent or behavior for all input data.
