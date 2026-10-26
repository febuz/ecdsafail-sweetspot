#!/usr/bin/env python3
"""Batch-inversion identities for the in-place point add (x2, y2) += (ox, oy) on secp256k1.

dx = x2 - ox, dy = y2 - oy, lambda = dy/dx, d' = ox - x3 (the leader's multiply-walk input).
  N = dx^3 + 3 ox dx^2 - dy^2  =>  d' = N / dx^2
  D = dx N                     =>  1/dx = N/D  and  1/d' = dx^3/D   (one inversion gives both)
  output side: dx = lambda'^2 - x3 - 2 ox with lambda' = (y3 + oy)/d'   (needs 1/d')
Checked on random point pairs; prints the pass count.
"""
import random

P = 2**256 - 2**32 - 977
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def inv(a):
    return pow(a, P - 2, P)


def add(a, b):
    (x1, y1), (x2, y2) = a, b
    l = 3 * x1 * x1 * inv(2 * y1) % P if a == b else (y2 - y1) * inv(x2 - x1) % P
    x3 = (l * l - x1 - x2) % P
    return x3, (l * (x1 - x3) - y1) % P


def mul(k, a):
    r = None
    while k:
        if k & 1:
            r = a if r is None else add(r, a)
        a, k = add(a, a), k >> 1
    return r


def main(trials=50):
    ok = 0
    for _ in range(trials):
        x2, y2 = mul(random.randrange(1, 2**64), G)
        ox, oy = mul(random.randrange(1, 2**64), G)
        dx, dy = (x2 - ox) % P, (y2 - oy) % P
        lam = dy * inv(dx) % P
        x3 = (lam * lam - x2 - ox) % P
        y3 = (lam * (ox - x3) - oy) % P
        dp = (ox - x3) % P
        n = (dx**3 + 3 * ox * dx * dx - dy * dy) % P
        dinv = inv(dx * n % P)
        lam2 = (y3 + oy) * inv(dp) % P
        ok += (dp == n * inv(dx * dx) % P and inv(dx) == n * dinv % P and inv(dp) == dx**3 * dinv % P
               and lam2 == lam and (lam2 * lam2 - x3 - 2 * ox) % P == dx)
    print(f"{ok} / {trials}")


if __name__ == "__main__":
    main()
