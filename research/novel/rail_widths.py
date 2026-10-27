#!/usr/bin/env python3
"""Per-step rail width bound for the circuit: max over samples of the two's-complement width of f and g at the
start of each step (and after it), plus a margin. Prints a Rust const array."""
import random
import sys

P = 2**256 - 2**32 - 977


def tw(v):
    return (v.bit_length() + 1) if v >= 0 else ((-v - 1).bit_length() + 1)


n, steps, margin = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
rnd = random.Random(2024)
mx = [0] * (steps + 1)
for k in range(n):
    d = rnd.randrange(1, P) if k > 2 else [1, 2, P - 1][k]
    d2, f, g = 1, P, d
    for i in range(steps):
        mx[i] = max(mx[i], tw(f), tw(g))
        if d2 > 0 and g & 1:
            d2, f, g = 2 - d2, g, (g - f) >> 1
        elif g & 1:
            d2, g = 2 + d2, (g + f) >> 1
        else:
            d2, g = 2 + d2, g >> 1
    mx[steps] = max(mx[steps], tw(f), tw(g))
w = [min(258, m + margin) for m in mx]
print(f"// {n} samples, margin {margin}; sum {sum(w)}")
print("pub const RAIL_W: [u16; %d] = [%s];" % (steps + 1, ",".join(map(str, w))))
