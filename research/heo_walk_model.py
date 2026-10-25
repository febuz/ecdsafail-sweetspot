#!/usr/bin/env python3
"""Exact integer model of the leader's HEO rail walk (heo.rs fwd_tick).

Rails start at (R1, R2) = (d + p, d). Tick t with envelope widths
(esw, ead), two's complement:
  resize both rails to esw (sign-extend / sign-truncate),
  c = R1 bit 0; if c: swap bits >= 1 of R1 and R2; R2[0] ^= c,
  E = R1 >> 1, resized to ead; R2 resized to ead,
  R2 <- R2 - E if sign(E) == sign(R2) else R2 + E   (mod 2^ead),
  R1 <- E.
A resize that truncates a value that does not fit, or an add that wraps,
is exactly where the gate-level circuit silently diverges from the
integer algorithm. `run` reports the first such event, if any.
"""
import sys
from pathlib import Path

P = 2**256 - 2**32 - 977
DATA = Path("/private/tmp/ecdsa-leader/src/point_add/skywalk_data")


def envelope(name):
    rows = [line.split() for line in (DATA / name).read_text().splitlines() if line.strip() and not line.startswith("#")]
    return [(int(a), int(b)) for a, b in rows]


def fits(value, width):
    return -(1 << (width - 1)) <= value < (1 << (width - 1))


def run(d, env, exact=False):
    """Walk d through the envelope. Returns (first_violation, final rails, ticks)."""
    r1, r2 = d + P, d
    for t, (esw, ead) in enumerate(env):
        if not exact and not (fits(r1, esw) and fits(r2, esw)):
            return ("swap-width", t), (r1, r2)
        if r1 & 1:
            hi1, hi2 = r1 >> 1, r2 >> 1
            r1, r2 = (hi2 << 1) | 1, (hi1 << 1) | ((r2 & 1) ^ 1)
        e = r1 >> 1
        if not exact and not (fits(e, ead) and fits(r2, ead)):
            return ("add-width", t), (r1, r2)
        new = r2 - e if (e < 0) == (r2 < 0) else r2 + e
        if not exact and not fits(new, ead):
            return ("add-overflow", t), (r1, r2)
        r1, r2 = e, new
    return None, (r1, r2)


if __name__ == "__main__":
    import random
    env = envelope("extended-middle-0.txt")
    rng = random.Random(1)
    finals = {}
    for _ in range(2000):
        d = rng.randrange(1, P)
        violation, final = run(d, env)
        exact_final = run(d, env, exact=True)[1]
        key = (violation[0] if violation else "ok", (exact_final[0] in (-1, 0, 1), exact_final[1] in (-1, 0, 1)))
        finals[key] = finals.get(key, 0) + 1
    print(len(env), "ticks;", finals)
