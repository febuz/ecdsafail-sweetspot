#!/usr/bin/env python3
"""Theoretical budget: how far can an independent divsteps-family point add go, and what must hold to reach ~850k T?

Each lever lists its assumption and status:
  M = measured in this repo,  T = textbook cost formula,  S = speculative (needs the named research item),
  L = also used by the leader (requires the user's OK before building).
Costs are Toffoli counts per point add (two inversion walks + square + coordinate ops).
"""
n, pad = 256, 24
W_AVG = 72315 / 540          # M: mean rail width over the 540-step envelope (rail_w.rs / width_check.py)


def scenario(name, ticks, rails_per_tick_w, rails_const, pay_per_tick, pay_fixed, tape_bits_per_tick,
             pack_per_tick, square, coords, carries_q, pay_q):
    rails = 2 * ticks * (rails_per_tick_w * W_AVG + rails_const)      # forward + reverse pass
    payload = ticks * pay_per_tick + pay_fixed
    pack = 2 * ticks * pack_per_tick
    div = rails + payload + pack
    t = 2 * div + square + coords
    tape = ticks * tape_bits_per_tick
    q = tape + pay_q + carries_q + 40
    return dict(name=name, rails=rails, payload=payload, pack=pack, div=div, t=t, q=q, score=t * q)


S = []
# 0: today's code (unit-test measured division 1.37M; square measured 137k)
S.append(scenario("0 today (DivPay 2d)", 540, 3, 40, 1450, 0, 5 / 3, 46, 137_000, 6_000, 258 + 256, 512))
# 1: backlog I2-I5 (BACKLOG.md), same architecture
S.append(scenario("1 backlog I2-I5", 535, 3, 35, 1450 + 0.29 * 640, 0, 1.6, 25, 137_000, 6_000, 258, 512))
# 2: + R1 jump ticks (S/L): 305 ticks (tail-truncated, worst 303-317), merged halvings, one Montgomery fold per tick
#    payload per tick: cswap n + signed add n + one +-p correction n + fold (subtract m*c', ~n) + compares ~150
#    rails per tick: cswap w + add w + 2 barrel stages 2w = 4w
S.append(scenario("2 + jump ticks (R1)", 305, 4, 40, 4 * 280 + 150, 0, 3, 25, 137_000, 6_000, 258, 512))
# 3: + swap-free walk (R2, S/L): fixed role alternation removes cswap on rails (w) and payload (n)
S.append(scenario("3 + swap-free schedule (R2)", 305, 3, 40, 3 * 280 + 150, 0, 3, 25, 137_000, 6_000, 258, 512))
# 4: + deferred modular correction (S): payload in a padded redundant form, the +-p correction folded every 8 ticks
#    (Solinas fold of the overflow bits, ~n per fold); per tick: add n + Montgomery fold n + 1/8 correction + 60
S.append(scenario("4 + deferred correction (S)", 305, 3, 40, 2 * 280 + 280 / 8 + 60, 0, 3, 25, 137_000, 6_000, 258, 2 * (n + pad)))
# 5: + rails read-only reverse (S): erase the tape with measurement and recompute letters only for the phase fix,
#    using a cheap letter-only rails pass that keeps the top window and low bits (approximate, research R3/R5).
#    Modelled as: the reverse pass costs 2w per tick instead of 3w.
def s5():
    d = scenario("5 + cheaper reverse pass (S)", 305, 2.5, 40, 2 * 280 + 280 / 8 + 60, 0, 3, 25, 137_000, 6_000, 258, 2 * (n + pad))
    return d
S.append(s5())
# 6: + square with deferred reduction and measurement-erased rows (T): ~n^2/2 rows + one Solinas fold, ~75k
S.append(scenario("6 + leaner square (T)", 305, 2.5, 40, 2 * 280 + 280 / 8 + 60, 0, 3, 18, 75_000, 4_000, 258, 2 * (n + pad)))
# 7: + payload fold merged into the add (S): one carry chain per tick computes v + u - m*c' (3-operand, carry-save
#    first layer of ~n Toffoli then one ripple n): ~1.6n instead of 2n; tape packed 3 ticks / 8 bits (2.67 b/tick)
S.append(scenario("7 + merged add+fold, denser tape (S)", 305, 2.5, 40, 1.6 * 280 + 280 / 8 + 60, 0, 8 / 3, 18, 75_000, 4_000, 258, 2 * (n + pad)))
# 8: + chunked carries in late ticks (T): carries 258 -> 40 at +n per add in the late third of the walk
S.append(scenario("8 + chunked late carries (T)", 305, 2.5, 40, 1.6 * 280 + 280 / 8 + 60 + 280 / 3, 0, 8 / 3, 18, 75_000, 4_000, 40, 2 * (n + pad)))

print(f"{'scenario':42s} {'rails/div':>10s} {'payload/div':>12s} {'T total':>10s} {'Q':>6s} {'score':>8s}")
for d in S:
    print(f"{d['name']:42s} {d['rails']:10,.0f} {d['payload']:12,.0f} {d['t']:10,.0f} {d['q']:6.0f} {d['score'] / 1e9:7.2f}B")

# 9: + deferred rail shifts (S, new): rails kept unnormalised for two ticks, one combined barrel per two ticks,
#    modelled as 2.25w per tick instead of 2.5w
d9 = scenario("9 + deferred rail shifts (S)", 305, 2.25, 40, 1.6 * 280 + 280 / 8 + 60, 0, 8 / 3, 18, 75_000, 4_000, 258, 2 * (n + pad))
print(f"{d9['name']:42s} {d9['rails']:10,.0f} {d9['payload']:12,.0f} {d9['t']:10,.0f} {d9['q']:6.0f} {d9['score'] / 1e9:7.2f}B")
