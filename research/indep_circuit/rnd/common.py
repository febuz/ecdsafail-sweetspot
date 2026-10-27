"""Shared helpers for the R16-R18 research harness: secp256k1 constants, seeded inputs, parallel sweeps, results.

Every experiment is a function f(d) -> dict of metrics for one input d in [1, p). `sweep` runs it on N inputs
(split over worker processes, reproducible by seed) and aggregates mean / max / quantiles per metric.
Results are written as small JSON files to results/ (no raw per-input data).
"""
import json
import math
import multiprocessing as mp
import os
import random
import time

P = 2**256 - 2**32 - 977
C = 2**32 + 977            # p = 2^256 - C (Solinas form)
N_BITS = 256
HERE = os.path.dirname(os.path.abspath(__file__))


def inputs(n, seed):
    rnd = random.Random(seed)
    return [rnd.randrange(1, P) for _ in range(n)]


def _chunk(args):
    fn, n, seed = args
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        out.append(fn(rnd.randrange(1, P)))
    return out


def sweep(fn, n, seed=1, workers=None):
    """Run fn on n random inputs; workers default to all cores. Returns aggregated metrics."""
    workers = workers or os.cpu_count() or 1
    per = [n // workers + (1 if i < n % workers else 0) for i in range(workers)]
    jobs = [(fn, k, seed * 1_000_003 + i) for i, k in enumerate(per) if k]
    t0 = time.time()
    if len(jobs) == 1:
        rows = _chunk(jobs[0])
    else:
        with mp.Pool(len(jobs)) as pool:
            rows = [r for part in pool.map(_chunk, jobs) for r in part]
    agg = {"n": n, "seed": seed, "seconds": round(time.time() - t0, 1)}
    for key in rows[0]:
        vals = sorted(r[key] for r in rows)
        if all(isinstance(v, bool) for v in vals):
            agg[key] = {"true": sum(vals), "false": len(vals) - sum(vals)}
            continue
        agg[key] = {
            "mean": round(sum(vals) / len(vals), 3),
            "max": vals[-1],
            "min": vals[0],
            "q99_99": vals[max(0, math.ceil(len(vals) * 0.9999) - 1)],
        }
    return agg


def save(name, payload):
    path = os.path.join(HERE, "results", f"{name}.json")
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
    return path
