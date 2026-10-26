#!/usr/bin/env python3
"""Count inputs whose rail width exceeds the 1,500-sample envelope (+margin) at any of the first 535 steps."""
import random
import sys

from divsteps_sim import P
from textbook_design import envelope


def widths(d, steps):
    d2, f, g = 1, P, d
    out = []
    for _ in range(steps):
        out.append(max(abs(f).bit_length(), abs(g).bit_length()) + 1)
        if d2 > 0 and g & 1:
            d2, f, g = 2 - d2, g, (g - f) >> 1
        elif g & 1:
            d2, g = 2 + d2, (g + f) >> 1
        else:
            d2, g = 2 + d2, g >> 1
    return out


n, steps = int(sys.argv[1]), 535
env0 = envelope(steps, margin=0)
rnd = random.Random(99)
worst = [0] * steps
for _ in range(n):
    for i, w in enumerate(widths(rnd.randrange(1, P), steps)):
        if w > worst[i]:
            worst[i] = w
over = max(w - e for w, e in zip(worst, env0))
print(f"{n} inputs: max excess over the 1,500-sample envelope (margin 0) = {over} bits; "
      f"margin 4 holds: {over <= 4}; sum of the {n}-input envelope = {sum(worst)}")
