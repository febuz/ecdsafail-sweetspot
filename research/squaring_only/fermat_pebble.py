#!/usr/bin/env python3
"""Division-free inversion a^-1 = a^(p-2) on secp256k1 using only squarings and multiplications, made reversible.

Modular squaring is 2-to-1, so each intermediate power is kept in a fresh 256-qubit register or recomputed later.
Optimal reversible pebbling of a line of L steps with k pebbles (Knill 1995):
    F(k, L) = min_m 2 F(k, m) + F(k-1, L-m),  F(k, 1) = 1,  F(1, L > 1) = inf
F counts the steps to put a pebble on node L and remove all the others; the result is uncomputed later at the same cost.
Point add: 2 inversions (lambda and its uncompute), each computed and uncomputed (x2), plus about 6 products.
Product cost is calibrated on the leader: a modular square-and-subtract is 34.1k T (`square` phase), and a
multiplication costs about 2x that. Width: x, y (512) + k pebble registers + 1 product workspace (256) + ~60 ancilla.
"""
import functools

L = 266            # optimal secp256k1 chain for p-2: ~253 squarings + 13 multiplications
T_SQ, T_MUL = 34_100, 68_200
LEADER = 741_719 * 1_234


@functools.lru_cache(None)
def F(k, n):
    if n == 0:
        return 0
    if n == 1:
        return 1
    if k == 1:
        return float("inf")
    return min(2 * F(k, m) + F(k - 1, n - m) for m in range(1, n))


def main():
    print(f"chain length {L}; leader score {LEADER / 1e6:.0f}M")
    print(" k  steps/inv   T (point add)   Q      score      vs leader")
    for k in range(2, 13):
        steps = F(k, L)
        if steps == float("inf") or steps > 1e12:
            print(f"{k:2d}  {steps:.1e} steps: exponential, not feasible")
            continue
        per_inv = steps * T_SQ * (1 + 13 / 266)  # mix of squarings and the few multiplications
        t = 2 * 2 * per_inv + 6 * T_MUL
        q = 512 + (k + 1) * 256 + 60
        print(f"{k:2d}  {steps:9,d}  {t / 1e6:10.1f}M  {q:5d}  {t * q / 1e9:8.1f}B   {t * q / LEADER:6.1f}x")


if __name__ == "__main__":
    main()
