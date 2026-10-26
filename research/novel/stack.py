#!/usr/bin/env python3
"""Stack leader techniques onto DivPay one at a time; keep a step only if the score drops.

Each step states where its numbers come from: M = this repo's model/measurement, C = community-measured effect in the
same GCD family (submission notes, research/novel/data/used_techniques.json), L = the leader's measured phase costs.
"""
N = 256
steps = []
T, Q = 2_160_433, 1_418  # DivPay T6 (Ontwerp sheet)
steps.append(("S0 DivPay T6 (divsteps, exact, generic primitives)", T, Q, "M", "start"))

# S1 jump: merge pure halvings into the add step, cap e<=3, one modular fold per tick (G28 + G25)
ticks = 317                       # M: worst case over 20k inputs (jump_divsteps.py)
pay_tick = 256 + 287 + 416 + 2 * 287 + 80   # swap, add/sub, mod fix, fold of <=4 halvings (2 const adds), compares
pay_old = 535 * (256 + 287 + 416 + 327)
rails_old = 178_000
rails_new = rails_old * (ticks * 4) / (535 * 2)          # swap+add (2w) + 2 barrel stages (2w) per tick
T = T - 2 * (pay_old - ticks * pay_tick) - 4 * (rails_old - rails_new)
Q = Q - 850 + ticks * 3                                   # letter: odd/swap bit + 2-bit shift per tick
steps.append(("S1 + multi-bit shift per tick, one fold per tick (G28, G25)", T, Q, "M",
              f"{ticks} ticks instead of 535 steps; tape {ticks * 3} bits instead of 850"))

T *= 1 - 0.035                                            # C: conditional replay -3.49% (4b7d727)
steps.append(("S2 + conditional replay on average-executed Toffoli (G26)", T, Q, "C", "-3.5% T (4b7d727)"))

T -= 8_000                                                # C/L: Karatsuba half-square recombination
steps.append(("S3 + Karatsuba square (G22)", T, Q, "C", "-8k T on a 38k square"))

Q -= 20                                                   # C: interleaved schedule / hosting -1.2..1.5% via Q
steps.append(("S4 + interleaved walk/replay, scratch hosting (G30, G04)", T, Q, "C", "-20 Q (aac98e9, bc7a792)"))

# S5 ping-pong + leapfrog: swap-free fixed schedule, forced steps, deep/flat choice, fitted rails, lever-A barrel.
# At this point the walk IS the leader's walk; costs from the leader's measured phases plus exactness (lf_tail refit).
T, Q = 741_645 + 43_000, 1_234 + 9
steps.append(("S5 + ping-pong, leapfrog walk, lever A (G29, G34, G35, G36)", T, Q, "L",
              "leader walk 350k + 357k T; +43k T and ~+9 Q to make it exact without grinding"))

# S6 complementary non-leader techniques on top
Q -= 3                                                    # M/estimate: Khattar-Gidney comparator ancillas
steps.append(("S6 + conditionally clean ancillae for window compares (unused)", T, Q, "M", "~-3 Q (estimate)"))
steps.append(("S7 + transcript radix packing (unused)", T, Q, "M", "0: leader tape measured at its local floor"))
steps.append(("S8 + spooky pebbling / Bennett on the tape (unused)", T, Q, "M", "0: flat trade (~7,100 T per qubit)"))

prev = None
print(f"{'step':66s} {'T':>10s} {'Q':>6s} {'score':>9s} {'delta':>8s}  src  basis")
for name, t, q, src, basis in steps:
    s = t * q
    d = "" if prev is None else f"{(s / prev - 1) * 100:+.1f}%"
    print(f"{name:66s} {t:10,.0f} {q:6d} {s / 1e9:8.3f}B {d:>8s}  {src}    {basis}")
    prev = s
print("\nreference: leader 0.915B (approximate, ground); Google low-gate 2.99B, low-qubit 3.17B")
