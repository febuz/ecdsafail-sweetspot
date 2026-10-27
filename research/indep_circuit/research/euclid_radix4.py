#!/usr/bin/env python3
"""Supports the 1,050 Q / 900k T paper design.
(1) Radix-4 iterations: ceil(bitlen(q)/2) per Euclid step (two quotient bits per iteration, SRT-style digit select).
(2) Shared rails + tape peak with ideal entropy coding of quotients under Gauss-Kuzmin, -log2 P(q),
    P(q) = -log2(1 - 1/(q+1)^2), against Elias-gamma (2 floor(log2 q) + 1).
"""
import math
import random
import sys

P = 2**256 - 2**32 - 977


def gk_bits(q):
    return -math.log2(-math.log2(1 - 1 / (q + 1) ** 2))


n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
rnd = random.Random(11)
r4, pk_gk, pk_eg = [], [], []
for _ in range(n):
    f, g = P, rnd.randrange(1, P)
    it, t_gk, t_eg, m_gk, m_eg = 0, 0.0, 0, 0, 0
    while g:
        q, r = divmod(f, g)
        it += (q.bit_length() + 1) // 2
        t_gk += gk_bits(q)
        t_eg += 2 * int(math.log2(q)) + 1
        f, g = g, r
        m_gk = max(m_gk, f.bit_length() + g.bit_length() + t_gk)
        m_eg = max(m_eg, f.bit_length() + g.bit_length() + t_eg)
    r4.append(it)
    pk_gk.append(m_gk)
    pk_eg.append(m_eg)
for name, v in (("radix-4 iterations", r4), ("shared peak, Gauss-Kuzmin ideal code", pk_gk), ("shared peak, Elias-gamma", pk_eg)):
    v.sort()
    print(f"{name:38s} mean {sum(v) / n:7.1f}  q99.99 {v[int(n * 0.9999) - 1]:7.1f}  max {v[-1]:7.1f}")
