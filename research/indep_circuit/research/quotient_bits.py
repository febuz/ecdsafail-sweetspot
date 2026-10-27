#!/usr/bin/env python3
"""R11/R12: circuit iterations of a bit-serial Euclid (Proos-Zalka style) for 256-bit inversion from p.
One iteration = one candidate quotient bit (compare + conditional subtract of a shifted g). Per Euclid step with
quotient q that is floor(log2 q) + 1 iterations; the circuit needs the worst-case total over all steps.
Also the binary-shift variant: subtract g * 2^k for the largest k with g 2^k <= f (one iteration per subtraction)."""
import random
import sys

P = 2**256 - 2**32 - 977
n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
rnd = random.Random(7)
tot, tot_sub = [], []
for _ in range(n):
    f, g, it, sub = P, rnd.randrange(1, P), 0, 0
    while g:
        q, r = divmod(f, g)
        it += q.bit_length()
        sub += bin(q).count("1")
        f, g = g, r
    tot.append(it)
    tot_sub.append(sub)
for name, v in (("quotient-bit iterations (compare each bit)", tot), ("set quotient bits (actual subtractions)", tot_sub)):
    v.sort()
    print(f"{name:45s} mean {sum(v) / n:6.1f}  q99.99 {v[int(n * 0.9999) - 1]}  max {v[-1]}")
