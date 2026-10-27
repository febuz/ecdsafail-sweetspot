#!/usr/bin/env python3
"""Paper budget for the Euclid shared-register path toward ~1,050 Q and ~900k T.

Measured inputs (research/, 20,000 random inputs):
  radix-4 Euclid iterations: max 240 (mean 216)        -> I = 240
  Euclid steps: max 185                                -> step boundaries are data-dependent within the I iterations
  shared rails + tape peak, ideal Gauss-Kuzmin coding: max 524 (Elias-gamma 551)
  mean rail width over the walk: ~128 (rails shrink from 256 to 0)
Per-iteration costs in Toffoli; the boundary block (swap + realign) is paid on every iteration because the step end
is data-dependent. Status: T textbook, S speculative, S! needs a new result.
"""
n, I, W = 256, 240, 128
SQUARE, COORDS = 75_000, 4_000


def budget(name, rails_fwd, rails_rev, payload, boundary, coding, workspace, tape_peak):
    per_it = rails_fwd + rails_rev + payload + boundary + coding
    div = I * per_it
    t = 2 * div + SQUARE + COORDS
    q = tape_peak + 2 * n + workspace
    return name, per_it, div, t, q


rows = [
    # A: textbook + S levers. Rails: digit select from a 12-bit top window (40) + select op among +-g, +-2g by two
    # measurement-erased ANDs per bit (2W) + one Gidney add (W); the 2-bit shift is a relabel. Payload: select among
    # +-b, +-2b (2n ANDs) + add (n) + amortised Solinas fold of the 2 growth bits (n/4), deferred correction (S).
    # Boundary: conditional swap of rails (W) and payload (n) + one-step realign (2W Fredkins), every iteration.
    budget("A  radix-4 SRT Euclid, known + S levers", 40 + 3 * W + 10, 40 + 3 * W + 10, 3 * n + n // 4,
           W + n + 2 * W + (2 * W), 12, 40, 551),
    # B: + payload selection fused into the adder (Q7-style inline products: 1 extra Toffoli per bit instead of 2 ANDs)
    budget("B  + fused payload select (S)", 40 + 3 * W + 10, 40 + 3 * W + 10, 2 * n + n // 4,
           W + n + 2 * W + (2 * W), 12, 40, 551),
    # C: + rails select fused too (2W per pass)
    budget("C  + fused rails select (S)", 40 + 2 * W + 10, 40 + 2 * W + 10, 2 * n + n // 4,
           W + n + 2 * W + (2 * W), 12, 40, 551),
    # D: + near-entropy quotient coding (block enumerative code, S) and dirty-borrowed workspace (R14, S): Q -> ~1,050;
    #    dirty adders cost +50% on the adds they replace (modelled on the payload add and the rails adds)
    budget("D  + near-entropy coding, dirty workspace (S)", 40 + 2 * W + 10 + W // 2, 40 + 2 * W + 10 + W // 2,
           2 * n + n // 4 + n // 2, W + n + 2 * W + (2 * W), 20, 14, 524),
    # E: + swap-free Euclid formulation (S!, R17): role alternation without conditional swaps, boundary block <= 100 T
    budget("E  + swap-free boundary <= 100 T (S!)", 40 + 2 * W + 10 + W // 2, 40 + 2 * W + 10 + W // 2,
           2 * n + n // 4 + n // 2, 100, 20, 14, 524),
    # F: + payload at ~2n per iteration including the dirty penalty (S!, R16: carry-save payload with one fold/4 its)
    budget("F  + payload <= 2n per iteration (S!)", 40 + 2 * W + 10 + W // 2, 40 + 2 * W + 10 + W // 2,
           2 * n, 100, 20, 14, 524),
]
print(f"{'design':48s} {'T/iter':>7s} {'T/div':>9s} {'T total':>10s} {'Q':>6s} {'score':>8s}")
for name, per_it, div, t, q in rows:
    print(f"{name:48s} {per_it:7.0f} {div:9,.0f} {t:10,.0f} {q:6d} {t * q / 1e9:7.2f}B")
