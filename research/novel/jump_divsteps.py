#!/usr/bin/env python3
"""Merge divsteps' pure halvings into the preceding add step (a barrel shift of e bits per tick): tick count,
shift distribution, and the fixed-length letter cost per tick for a cap e <= E (longer runs split into extra ticks)."""
import math
import random
import sys
from collections import Counter

P = 2**256 - 2**32 - 977


def run(d, steps=535):
    d2, f, g = 1, P, d
    kinds = []
    for _ in range(steps):
        if d2 > 0 and g & 1:
            d2, f, g = 2 - d2, g, (g - f) >> 1
            kinds.append("s")
        elif g & 1:
            d2, g = 2 + d2, (g + f) >> 1
            kinds.append("o")
        else:
            d2, g = 2 + d2, g >> 1
            kinds.append("e")
    return kinds


n = int(sys.argv[1])
rnd = random.Random(5)
adds, runs, worst_ticks = [], Counter(), {}
for _ in range(n):
    k = run(rnd.randrange(1, P))
    adds.append(sum(c != "e" for c in k))
    r = 0
    for c in k + ["o"]:
        if c == "e":
            r += 1
        else:
            runs[r] += 1
            r = 0
    for E in (3, 7):
        t = sum(1 + (x // (E + 1)) for x in [len(s) for s in "".join("x" if c != "e" else "e" for c in k).split("x")])
        worst_ticks[E] = max(worst_ticks.get(E, 0), t)
tot = sum(runs.values())
print(f"{n} inputs: add steps mean {sum(adds) / n:.1f}, max {max(adds)}; worst-case ticks with cap e<=3: {worst_ticks[3]}, e<=7: {worst_ticks[7]}")
print("even-run length distribution:", {k: round(v / tot, 4) for k, v in sorted(runs.items())[:9]})
for E in (3, 7):
    ticks = worst_ticks[E]
    bits = ticks * (math.log2(3) + math.log2(E + 1))
    print(f"cap e<={E}: {ticks} ticks x (trit + {math.log2(E + 1):.0f}-bit shift) = {bits:.0f} letter bits (vs 535 x log2 3 = {535 * math.log2(3):.0f})")
