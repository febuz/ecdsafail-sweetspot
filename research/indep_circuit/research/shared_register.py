#!/usr/bin/env python3
"""R11 measurement: can rails + tape share one register of ~520 bits (Proos-Zalka) for a 256-bit inversion from p?

For each walk we track, at every step, bits(f) + bits(g) + tape bits written so far, and report the maximum.
Walks: classic Euclid (q = f // g), nearest-integer Euclid (|r| <= g/2, signed quotient), and half-delta divsteps
(ternary letters at log2(3) bits). Tape codes: Elias-gamma of q (2 floor(log2 q) + 1 bits), plus 1 sign bit for the
nearest variant; divsteps: log2(3) per step (ideal) and 5/3 (3 trits in 5 bits).
"""
import math
import random
import sys

P = 2**256 - 2**32 - 977


def bl(v):
    return abs(v).bit_length()


def euclid(d, nearest):
    f, g, tape, peak, steps, qmax = P, d, 0.0, 0, 0, 0
    while g:
        if nearest:
            q = (2 * f + g) // (2 * g)          # round(f / g)
            r = f - q * g
            tape += 2 * int(math.log2(abs(q))) + 1 + 1 if q else 1
            f, g = g, abs(r)
        else:
            q, r = divmod(f, g)
            tape += 2 * int(math.log2(q)) + 1
            f, g = g, r
        qmax = max(qmax, abs(q))
        steps += 1
        peak = max(peak, bl(f) + bl(g) + tape)
    return peak, steps, tape, qmax


def divsteps(d, bits_per_step):
    d2, f, g, tape, peak = 1, P, d, 0.0, 0
    for _ in range(535):
        if d2 > 0 and g & 1:
            d2, f, g = 2 - d2, g, (g - f) >> 1
        elif g & 1:
            d2, g = 2 + d2, (g + f) >> 1
        else:
            d2, g = 2 + d2, g >> 1
        tape += bits_per_step
        peak = max(peak, bl(f) + bl(g) + 1 + tape)
    return peak


n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
rnd = random.Random(31)
res = {"euclid": [], "nearest": [], "div_ideal": [], "div_5/3": []}
st = {"euclid": [], "nearest": []}
qm = {"euclid": 0, "nearest": 0}
for _ in range(n):
    d = rnd.randrange(1, P)
    for k, near in (("euclid", False), ("nearest", True)):
        pk, s, tp, q = euclid(d, near)
        res[k].append(pk)
        st[k].append(s)
        qm[k] = max(qm[k], q)
    res["div_ideal"].append(divsteps(d, math.log2(3)))
    res["div_5/3"].append(divsteps(d, 5 / 3))
for k, v in res.items():
    v.sort()
    extra = f", steps mean {sum(st[k]) / n:.1f} max {max(st[k])}, max |q| {qm[k]}" if k in st else ""
    print(f"{k:10s}: shared rails+tape peak mean {sum(v) / n:6.1f}, q99.99 {v[int(n * 0.9999) - 1]}, max {v[-1]}{extra}")
