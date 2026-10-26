#!/usr/bin/env python3
"""Tail of the hddivsteps iteration count needed to reach g = 0 (start f = p, g = d uniform)."""
import random
import sys
from collections import Counter

P = 2**256 - 2**32 - 977


def steps(d):
    d2, f, g, i = 1, P, d, 0
    while g:
        if d2 > 0 and g & 1:
            d2, f, g = 2 - d2, g, (g - f) >> 1
        elif g & 1:
            d2, g = 2 + d2, (g + f) >> 1
        else:
            d2, g = 2 + d2, g >> 1
        i += 1
    return i


n, seed = int(sys.argv[1]), int(sys.argv[2])
rnd = random.Random(seed)
c = Counter(steps(rnd.randrange(1, P)) for _ in range(n))
tot = 0
print(f"n={n} mean={sum(k * v for k, v in c.items()) / n:.1f} max={max(c)}")
for k in sorted(c, reverse=True):
    tot += c[k]
    if k % 5 == 0 or tot < 30:
        print(f"  P(steps > {k - 1}) = {tot / n:.2e}")
    if tot > n * 0.05:
        break
