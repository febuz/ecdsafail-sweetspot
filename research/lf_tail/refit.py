#!/usr/bin/env python3
"""Refit the walk's width table and tick count for a rule variant at a target failure rate per leg.

Input: lf_tail full-mode JSON (per-tick histogram `tmax` of need - leader table, max over columns, and the
variant's own park-tick histogram). For each R >= 122: walks parking after R fail; the remaining budget is
spread over ticks by a union bound (greedy: lower the tick whose next bit costs the least failure mass).
w[t] < 0 means the variant can run tick t narrower than the leader's table. Union bound = conservative but
the same for every variant, so differences between variants are the signal.
Cost: C_BIT T per bit-tick (sum w) + C_TICK T per extra tick, relative to the leader's 122-tick table.
Usage: refit.py run.json [--targets 1e-4,1e-5] [--c-bit 23] [--c-tick 4600]
"""
import argparse
import json

import numpy as np


def refit_w(d, target, r):
    """Union-bound width offsets w[t] (vs the leader table) for R = r, or None if park alone breaks the target."""
    n = d["samples"]
    lo = d["tmax_from"]
    h = np.array(d["tmax"], float) / n
    late = (np.array(d["park_tick_hist"], float) / n)[::-1].cumsum()[::-1]
    budget = target - (late[r + 1] if r + 1 < len(late) else 0.0)
    if budget < 0:
        return None
    w = np.array([np.flatnonzero(row)[-1] if row.any() else 0 for row in h])
    spent = 0.0
    while True:
        cost = np.where(w > 0, h[np.arange(len(w)), w], np.inf)
        t = int(cost.argmin())
        if not np.isfinite(cost[t]) or spent + cost[t] > budget:
            break
        spent += cost[t]
        w[t] -= 1
    return w + lo


def refit(d, target, c_bit, c_tick):
    n = d["samples"]
    lo = d["tmax_from"]
    h = np.array(d["tmax"], float) / n  # [tick][bin]
    surv = h[:, ::-1].cumsum(1)[:, ::-1]  # surv[t][b] = P(ex >= lo + b)
    pt = np.array(d["park_tick_hist"], float) / n
    late = pt[::-1].cumsum()[::-1]  # late[k] = P(park >= k)
    best = None
    for r in range(118, 141):
        park_fail = late[r + 1] if r + 1 < len(late) else 0.0
        budget = target - park_fail
        if budget < 0:
            continue
        top = np.array([np.flatnonzero(row)[-1] if row.any() else 0 for row in h])  # w = lo + top: all pass
        w = top.copy()
        spent = 0.0
        while True:
            # lowering w[t] to w-1 makes walks with ex == lo + w[t] fail
            cost = np.where(w > 0, h[np.arange(len(w)), w], np.inf)
            t = int(cost.argmin())
            if not np.isfinite(cost[t]) or spent + cost[t] > budget:
                break
            spent += cost[t]
            w[t] -= 1
        # the walk only exists on ticks < r; ticks past 122 are costed per tick, ticks dropped below 122 save
        wr = (w + lo)[: min(r, len(w))]
        bits = int(wr.sum())
        extra = c_tick * (r - 122)
        tot = c_bit * bits + extra
        if best is None or tot < best[0]:
            best = (tot, r, bits, park_fail, spent)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--targets", default="1e-4,1e-5")
    ap.add_argument("--c-bit", type=float, default=23)
    ap.add_argument("--c-tick", type=float, default=4600)
    a = ap.parse_args()
    for path in a.runs:
        d = json.load(open(path))
        for target in map(float, a.targets.split(",")):
            b = refit(d, target, a.c_bit, a.c_tick)
            if b is None:
                print(f"{path} {target:.0e}: unreachable")
                continue
            tot, r, bits, pf, sp = b
            print(f"{path} {target:.0e}: R {r} ({r - 122:+d}), width {bits:+d} bit-ticks vs leader table, "
                  f"park fail {pf:.1e} + width fail {sp:.1e}, ~{tot:+,.0f} T")


if __name__ == "__main__":
    main()
