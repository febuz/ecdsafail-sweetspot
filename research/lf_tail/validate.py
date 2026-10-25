#!/usr/bin/env python3
"""Validate the lf_tail walk model against real circuit outcomes.

For each input pair (target, offset) the point add runs two walks: the divide on d = x2 - x1 and the
multiply leg on d' = x2 - x3. The model predicts a failure when either walk overflows the fitted width
table or does not park in 122 ticks. Compares predictions with the shots the simulator reports failing.
Usage: validate.py ops.bin (--seed S --shots N | --fiat-shamir) [--failing pickle]
"""
import argparse
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis"))
from live_width import fiat_shamir_inputs, mul, N  # noqa: E402

P = 2**256 - 2**32 - 977
BIN = Path(__file__).resolve().parent / "target/release/lf_tail"


def inputs(args):
    if args.fiat_shamir:
        return fiat_shamir_inputs(args.ops)
    rng, out = random.Random(args.seed), []
    for _ in range(args.shots):
        while True:
            t, o = mul(rng.randrange(1, N)), mul(rng.randrange(1, N))
            if t[0] != o[0]:
                break
        out.append((t, o))
    return out


def predict(pairs):
    ds = []
    for (x1, y1), (x2, y2) in pairs:
        lam = (y2 - y1) * pow(x2 - x1, -1, P) % P
        x3 = (lam * lam - x1 - x2) % P
        ds += [(x2 - x1) % P, (x2 - x3) % P]
    out = subprocess.run([str(BIN), "0", "0", "--stdin"], input="\n".join(hex(d) for d in ds), capture_output=True, text=True).stdout.splitlines()
    bad = [("first_over=None parked=true" not in line.split("|")[1]) for line in out]
    return [(bad[2 * i], bad[2 * i + 1]) for i in range(len(pairs))]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ops", type=Path)
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--fiat-shamir", action="store_true")
    ap.add_argument("--failing", type=Path, help="pickle with the simulator's failing inputs (trace_rails output)")
    args = ap.parse_args()
    pairs = inputs(args)
    pred = predict(pairs)
    flagged = [i for i, (a, b) in enumerate(pred) if a or b]
    print(f"shots {len(pairs)}; model flags {len(flagged)} (divide {sum(a for a, _ in pred)}, multiply {sum(b for _, b in pred)})")
    if args.failing:
        import pickle
        real = {(f["target"], f["offset"]) for f in pickle.load(open(args.failing, "rb"))["failing"]}
        real_idx = {i for i, p in enumerate(pairs) if p in real}
        print(f"real failing {len(real_idx)}; both {len(real_idx & set(flagged))}; model-only {sorted(set(flagged) - real_idx)}; real-only {sorted(real_idx - set(flagged))}")
