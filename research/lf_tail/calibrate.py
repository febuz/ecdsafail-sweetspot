#!/usr/bin/env python3
"""Calibrate a variant's refit table against the exact joint failure rate.

refit.py's union bound only shapes the per-tick widths; the true rate needs the walks jointly. For a scale k
on the union-bound budget, write table = leader table + w[t] (all five columns), run lf_tail with it and count
failing walks exactly from the records (width excess >= 1 at any tick, or parked after R). Bisect k so the
exact rate per leg meets the target, then report the cost of the cheapest R.
Usage: calibrate.py run.json target n seed [--env "LF_..=.. ..."] [--rs 122,123,124,125]
"""
import argparse
import os
import subprocess
import tempfile

import numpy as np

from refit import json, refit_w

HERE = os.path.dirname(os.path.abspath(__file__))


def exact_rate(w, r, n, seed, env):
    lead = np.loadtxt(os.path.join(HERE, "a2_R122_steps.txt"), comments="#").astype(int)
    tab = lead + w[:, None]
    with tempfile.TemporaryDirectory() as td:
        tp, rp = os.path.join(td, "tab.txt"), os.path.join(td, "rec.txt")
        np.savetxt(tp, tab, fmt="%d")
        e = dict(os.environ, LF_SLACK="0,1,1,0,0", LF_TABLE=tp, LF_RECORDS=rp, **env)
        subprocess.run([os.path.join(HERE, "target/release/lf_tail"), str(n), str(seed)], env=e, check=True, stdout=subprocess.DEVNULL)
        fails = 0
        for line in open(rp):
            pt, ex = line.split()
            if int(pt) > r or max(int(v) for v in ex.split(",")) >= 1:
                fails += 1
    return fails / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("target", type=float)
    ap.add_argument("n", type=int)
    ap.add_argument("seed", type=int)
    ap.add_argument("--env", default="")
    ap.add_argument("--rs", default="122,123,124,125,126")
    ap.add_argument("--c-bit", type=float, default=23)
    ap.add_argument("--c-tick", type=float, default=4600)
    a = ap.parse_args()
    env = dict(kv.split("=") for kv in a.env.split())
    d = json.load(open(a.run))
    best = None
    for r in map(int, a.rs.split(",")):
        lo, hi = 1.0, 64.0  # scale on the union-bound budget; larger = narrower table
        sol = None
        for _ in range(7):
            k = (lo * hi) ** 0.5
            w = refit_w(d, a.target * k, r)
            if w is None:
                hi = k
                continue
            rate = exact_rate(w, r, a.n, a.seed, env)
            if rate <= a.target:
                sol, lo = (w, rate), k
            else:
                hi = k
        if sol is None:
            w = refit_w(d, a.target, r)
            if w is None:
                print(f"R {r}: unreachable")
                continue
            sol = (w, exact_rate(w, r, a.n, a.seed, env))
        w, rate = sol
        cost = a.c_bit * int(w.sum()) + a.c_tick * (r - 122)
        print(f"R {r}: width {int(w.sum()):+d} bit-ticks, exact rate {rate:.2e}, ~{cost:+,.0f} T", flush=True)
        if rate <= a.target and (best is None or cost < best[0]):
            best = (cost, r, int(w.sum()), rate)
    print(f"BEST {a.run} {a.env or 'ref'} @ {a.target:.0e}: {best}")


if __name__ == "__main__":
    main()
