#!/usr/bin/env python3
"""Locate where an approximate circuit goes wrong, using live-wire snapshots.

For each target value V (lambda, -lambda, x3, ...) and bit i, find the
wire whose value equals bit i of V on every *passing* shot, then report
how many *failing* shots disagree on those wires. A phase whose output is
already wrong for failing shots is where the error was introduced.
"""
import json
import pickle
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
from live_width import N, P, add, mul  # noqa: E402


def inputs(seed, shots):
    rng = random.Random(seed)
    out = []
    for _ in range(shots):
        while True:
            t, o = mul(rng.randrange(1, N)), mul(rng.randrange(1, N))
            if t[0] != o[0]:
                break
        out.append((t, o))
    return out


def main(snapshot_path, report_path, seed, shots):
    pts = inputs(seed, shots)
    report = json.load(open(report_path))
    failing_targets = {tuple(f["target"]) for f in report["failing_inputs"]}
    fail = [i for i, (t, _) in enumerate(pts) if tuple(t) in failing_targets]
    passing_mask = sum(1 << i for i in range(shots) if i not in set(fail))
    lam = [(t[1] - o[1]) * pow(t[0] - o[0], -1, P) % P for t, o in pts]
    x3 = [add(t, o)[0] for t, o in pts]
    values = {"lambda": lam, "-lambda": [(-v) % P for v in lam], "x3": x3,
              "x2-x3": [(o[0] - add(t, o)[0]) % P for t, o in pts], "x3-x2": [(add(t, o)[0] - o[0]) % P for t, o in pts], "x1-x2": [(t[0] - o[0]) % P for t, o in pts], "y1-y2": [(t[1] - o[1]) % P for t, o in pts]}
    snaps = pickle.load(open(snapshot_path, "rb"))
    for op, snap in sorted(snaps.items()):
        wires = snap["values"]
        by_vector = {}
        for wire, vector in wires.items():
            by_vector.setdefault(vector & passing_mask, wire)
        print(f"op {op}: {len(wires)} live wires, {len(fail)} failing shots")
        for name, vals in values.items():
            found, wrong_shots = 0, set()
            for bit in range(256):
                vector = sum(((v >> bit) & 1) << i for i, v in enumerate(vals))
                wire = by_vector.get(vector & passing_mask)
                if wire is None:
                    continue
                found += 1
                for i in fail:
                    if (wires[wire] >> i & 1) != (vector >> i & 1):
                        wrong_shots.add(i)
            if found:
                print(f"   {name:8s} bits located {found:3d}/256; failing shots already wrong here: {len(wrong_shots)}/{len(fail)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
