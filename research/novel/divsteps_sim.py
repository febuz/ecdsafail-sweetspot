#!/usr/bin/env python3
"""Classical reference for the novel design's inversion: Bernstein-Yang half-delta divsteps (hddivsteps).

State (delta, f, g) with f odd; 2*delta is kept as an integer (starts at 1, i.e. delta = 1/2).
  if delta > 0 and g odd:  (delta, f, g) <- (1 - delta, g, (g - f) / 2)
  elif g odd:              (delta, f, g) <- (1 + delta, f, (g + f) / 2)
  else:                    (delta, f, g) <- (1 + delta, f, g / 2)
Start f = p, g = d. After a fixed 591 iterations g = 0 and f = +-1 for every 0 < d < p (sipa's bound).
The payload tracks u, v (mod p) with u*d = f*2^-i (mod p)... checked here as d * (u / f) == 1 at the end.
Prints: correctness count, max iterations to reach g = 0, per-iteration width quantiles of f and g.
"""
import random
import sys

P = 2**256 - 2**32 - 977
STEPS = 591


def width(x):
    return (abs(x)).bit_length() + 1  # two's complement width


def run(d, track=True):
    d2, f, g = 1, P, d
    u, v = 0, 1  # f = u*d * 2^-i ... (mod p) invariant: f == u*d*2^i? we keep f ≡ u·d·(2^-i)^-1 style via halving mod p
    half = (P + 1) // 2
    widths = []
    done = None
    for i in range(STEPS):
        if track:
            widths.append((width(f), width(g)))
        if g == 0 and done is None:
            done = i
        if d2 > 0 and g & 1:
            d2, f, g, u, v = 2 - d2, g, (g - f) // 2, v, (v - u) * half % P
        elif g & 1:
            d2, g, v = 2 + d2, (g + f) // 2, (v + u) * half % P
        else:
            d2, g, v = 2 + d2, g // 2, v * half % P
    # invariants: f ≡ u·d·0 + ... ; we use u as the cofactor of f relative to g's start (g0 = d -> v0 = 1, f0 = p -> u0 = 0)
    ok = g == 0 and abs(f) == 1 and (u * d * f) % P == 1 % P if False else (g == 0 and abs(f) == 1)
    inv = (u * f) % P  # f = u·d (mod p) up to the tracked 2-powers
    return ok, done, widths, inv


def main(n=int(sys.argv[1]) if len(sys.argv) > 1 else 3000):
    rnd = random.Random(7)
    good = inv_ok = 0
    worst = 0
    per = [[] for _ in range(STEPS)]
    for _ in range(n):
        d = rnd.randrange(1, P)
        ok, done, w, inv = run(d)
        good += ok
        inv_ok += (inv * d) % P == 1
        worst = max(worst, done if done is not None else STEPS)
        for i, (a, b) in enumerate(w):
            per[i].append(max(a, b))
    print(f"{n} inputs: g = 0 and f = +-1 after {STEPS} steps: {good}/{n}; payload gives d^-1: {inv_ok}/{n}; "
          f"latest step reaching g = 0: {worst}")
    tot_max = tot_med = 0
    for i in range(STEPS):
        s = sorted(per[i])
        tot_max += s[-1]
        tot_med += s[len(s) // 2]
        if i % 100 == 0 or i == STEPS - 1:
            print(f"  step {i:3d}: rail width median {s[len(s) // 2]:3d}, max {s[-1]:3d}")
    print(f"sum over steps of max rail width (per rail): max-envelope {tot_max}, median {tot_med}")


if __name__ == "__main__":
    main()
