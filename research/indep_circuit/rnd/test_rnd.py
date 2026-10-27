#!/usr/bin/env python3
"""Quick correctness tests for the R16-R18 harness (seconds on a laptop). Run: python3 test_rnd.py"""
import random

from common import P
from r16_payload.payload_schemes import p1_exact, p1_lazy_16
from r17_swapfree.euclid_variants import c0, c1, c2, radix4_digits
from r18_coding.codes import DH, DH_DEC, c1_symbols, eg_dec, eg_enc, measure, prefix_decode


def test_radix4_digits():
    rnd = random.Random(1)
    for _ in range(200):
        g = rnd.randrange(1, P)
        f = rnd.randrange(g, P)
        digits, r = radix4_digits(f, g)
        assert all(-2 <= d <= 2 for _, d in digits)
        assert abs(r) < g
        assert f == sum(d * g * 4**j for j, d in digits) + r


def test_variants_invert():
    for d in [1, 2, 3, P - 1, 2**255, 12345] + [random.Random(2).randrange(1, P) for _ in range(30)]:
        for fn in (c0, c1, c2):
            assert fn(d)["ok"], (fn.__name__, d)


def test_payload_schemes():
    for d in [1, 2, P - 1] + [random.Random(3).randrange(1, P) for _ in range(20)]:
        assert p1_exact(d)["ok"]
        assert p1_lazy_16(d)["ok"]


def test_codes_round_trip():
    for q in list(range(1, 300)) + [2**40 + 7]:
        v, i = eg_dec(eg_enc(q), 0)
        assert v == q
    rnd = random.Random(4)
    for _ in range(20):
        syms = c1_symbols(rnd.randrange(1, P))
        assert prefix_decode("".join(DH[s] for s in syms), DH_DEC) == syms
        m = measure(rnd.randrange(1, P))
        assert m["EG_ok"] and m["DH_ok"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
