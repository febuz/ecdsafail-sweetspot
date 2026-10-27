#!/usr/bin/env python3
"""R16: payload schemes for the radix-4 nearest Euclid walk (C1 of r17), checked for correctness and range.

The payload pair follows the rails: when the walk does f -= d * 4^j * g, the payload does a -= d * 4^j * b (mod p),
seeded (a, b) = (0, y) so that at the end a = +-y/d. A scheme is a class with step(d, j) / end_step(sign) /
result(); `check` runs it on the walk and verifies a == y * d^-1 (mod p), and reports per-iteration operation counts
and the largest register width reached (for redundant-range schemes).

Schemes:
  P1_exact   t = b * 4^j kept by modular quartering each iteration (exact, canonical range): baseline costs
  P1_lazy_F  P1 with the subtraction kept in a padded redundant range and a Solinas fold every F iterations
  P2_scaled  TODO (the R16 target): global per-iteration scaling so that no positional factor 4^j is needed
"""
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from common import C, P, save, sweep  # noqa: E402
from r17_swapfree.euclid_variants import radix4_digits  # noqa: E402

INV4 = pow(4, -1, P)


class P1Exact:
    def __init__(self, y):
        self.a, self.b = 0, y
        self.ops = {"quarter": 0, "select_add": 0, "correction": 0}
        self.maxw = 256

    def begin_step(self, k):
        self.t = self.b * pow(4, k, P) % P        # circuit: k data-dependent doublings or a lookup (counted)
        self.ops["quarter"] += k

    def step(self, d, j, first):
        if not first:
            self.t = self.t * INV4 % P
            self.ops["quarter"] += 1
        self.a = (self.a - d * self.t) % P
        self.ops["select_add"] += 1
        self.ops["correction"] += 1

    def end_step(self, sign):
        self.a, self.b = self.b, sign * self.a % P


class P1Lazy(P1Exact):
    """a is kept as an integer in [0, 2^(256+pad)); the overflow above 2^256 is folded (H*2^256 = H*C) every F its."""

    def __init__(self, y, fold_every):
        super().__init__(y)
        self.F = fold_every
        self.since = 0
        self.ops["fold"] = 0

    def step(self, d, j, first):
        if not first:
            self.t = self.t * INV4 % P
            self.ops["quarter"] += 1
        self.a = self.a - d * self.t + 3 * P      # keep non-negative with a constant offset (multiple of p)
        self.ops["select_add"] += 1
        self.since += 1
        self.maxw = max(self.maxw, self.a.bit_length())
        if self.since >= self.F:
            h, l = divmod(self.a, 2**256)
            self.a = l + h * C
            self.ops["fold"] += 1
            self.since = 0

    def end_step(self, sign):
        a = self.a % P                             # step end: one canonical reduction (counted as correction)
        self.ops["correction"] += 1
        self.a, self.b = self.b, sign * a % P


def check(d, make):
    y = (d * 0x9E3779B97F4A7C15 + 12345) % P or 1    # deterministic payload input per d
    s = make(y)
    f, g = P, d
    its = 0
    while g:
        digits, r = radix4_digits(f, g)
        s.begin_step(digits[0][0])
        for idx, (j, dj) in enumerate(digits):
            s.step(dj, j, idx == 0)
            its += 1
        sign = -1 if r < 0 else 1
        s.end_step(sign)
        f, g = g, abs(r)
    a = s.a % P
    ok = a in (y * pow(d, -1, P) % P, (-y * pow(d, -1, P)) % P)
    res = {"ok": ok, "iterations": its, "max_width": s.maxw}
    res.update({f"ops_{k}": v for k, v in s.ops.items()})
    return res


def p1_exact(d):
    return check(d, P1Exact)


def lazy(F):
    def fn(d):
        return check(d, lambda y: P1Lazy(y, F))
    fn.__name__ = f"p1_lazy_{F}"
    return fn


def p1_lazy_1(d):
    return check(d, lambda y: P1Lazy(y, 1))


def p1_lazy_4(d):
    return check(d, lambda y: P1Lazy(y, 4))


def p1_lazy_16(d):
    return check(d, lambda y: P1Lazy(y, 16))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out = {}
    for name, fn in (("P1_exact", p1_exact), ("P1_lazy_F1", p1_lazy_1), ("P1_lazy_F4", p1_lazy_4), ("P1_lazy_F16", p1_lazy_16)):
        out[name] = sweep(fn, n, seed)
        a = out[name]
        print(f"{name:12s} ok {a['ok']}  iterations max {a['iterations']['max']}  max_width {a['max_width']['max']}  "
              + "  ".join(f"{k[4:]} {v['mean']}" for k, v in a.items() if k.startswith("ops_")))
    print("saved", save(f"r16_payload_n{n}_s{seed}", out))
