#!/usr/bin/env python3
"""Cheapest widening of the leader's walk for a target failure rate per leg.

Input: lf_tail failing-walk records ("park_tick ex_0,...,ex_121": bits the exact walk needs beyond the
fitted table per tick) from N sampled walks. Plan = extra ticks R' - 122 plus per-tick extra bits w[t].
A walk is fixed when park_tick <= R' and ex[t] <= w[t] for all t. For each R', walks that cannot park
are left failing, then the remaining failure budget is spent by peeling: repeatedly leave failing the
walk whose removal lowers sum(w) most. Cost in Toffoli: C_BIT per extra bit per tick (all four
traversals) + C_TICK per extra tick (both legs, payload included); measured from the stream.
Usage: widen.py records N [--targets 1e-5,1e-6,1e-7] [--c-bit 20] [--c-tick 4600]
"""
import argparse

import numpy as np


def load(path):
    pt, ex = [], []
    for line in open(path):
        a, b = line.split()
        pt.append(int(a))
        ex.append([int(v) for v in b.split(",")])
    return np.array(pt), np.clip(np.array(ex), 0, None)


def shrink(ex, budget, c_bit=1.0):
    """Start from w = max ex (every walk fixed); repeatedly lower the w[t] whose decrement newly breaks
    the fewest walks, while the broken count stays within budget."""
    w = ex.max(0) if len(ex) else np.zeros(ex.shape[1], int)
    ok = np.ones(len(ex), bool)
    broken = 0
    while True:
        hit = (ex == w) & ok[:, None] & (w > 0)
        cost = hit.sum(0).astype(float)
        cost[w == 0] = np.inf
        t = int(cost.argmin())
        if not np.isfinite(cost[t]) or broken + cost[t] > budget:
            return w, broken
        newly = hit[:, t]
        ok &= ~newly
        broken += int(newly.sum())
        w[t] -= 1


def peel(ex, budget):
    """Leave up to `budget` walks failing so that sum over t of max(ex[t]) is smallest (greedy)."""
    keep = np.ones(len(ex), bool)
    for _ in range(budget):
        if not keep.any():
            break
        sub = ex[keep]
        top = sub.max(0)
        # gain of dropping walk i: per tick, top - (max without i) where i is the unique max
        order = np.sort(sub, 0)
        second = order[-2] if len(sub) > 1 else np.zeros_like(top)
        is_top = sub == top
        unique = is_top.sum(0) == 1
        gain = ((is_top & unique) * (top - second)).sum(1)
        if gain.max() <= 0:
            break
        keep[np.flatnonzero(keep)[gain.argmax()]] = False
    w = ex[keep].max(0) if keep.any() else np.zeros(ex.shape[1], int)
    return w, int((~keep).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("records")
    ap.add_argument("n", type=float)
    ap.add_argument("--targets", default="1e-4,1e-5,1e-6,1e-7")
    ap.add_argument("--c-bit", type=float, default=23)
    ap.add_argument("--c-tick", type=float, default=4600)
    args = ap.parse_args()
    pt, ex = load(args.records)
    print(f"{len(pt)} failing walks of {args.n:.0f} ({len(pt) / args.n:.2e} per leg); park tick > 122: {(pt > 122).sum()}")
    for target in map(float, args.targets.split(",")):
        budget = int(target * args.n)
        best = None
        for r in range(122, 141):
            late = int((pt > r).sum())
            if late > budget:
                continue
            w, dropped = shrink(ex[pt <= r].copy(), budget - late)
            cost = args.c_bit * w.sum() + args.c_tick * (r - 122)
            if best is None or cost < best[0]:
                best = (cost, r, w, late + dropped)
        if best is None:
            print(f"target {target:.0e}: not reachable within 140 ticks")
            continue
        cost, r, w, left = best
        lam = 2 * 9024 * left / args.n
        ticks = ", ".join(f"t{t}+{v}" for t, v in enumerate(w) if v)
        print(f"target {target:.0e}/leg: ticks {r} (+{r - 122}), extra bit-ticks {w.sum()}, ~{cost:,.0f} T "
              f"({cost / 741719 * 100:.2f}%), left failing {left} -> lambda {lam:.3f} on 9,024 shots\n  {ticks}")


if __name__ == "__main__":
    main()
