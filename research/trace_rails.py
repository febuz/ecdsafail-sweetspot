#!/usr/bin/env python3
"""Capture leapfrog rail/payload wire values at builder-traced ticks (variant F)."""
import ast
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
from live_width import run  # noqa: E402

log, ops, out, shots, seed = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
import re
points = []
for line in open(log):
    if line.startswith("SWEET "):
        head = line.split()
        lists = [ast.literal_eval(x) for x in re.findall(r"\[[0-9, ]*\]", line)]
        pay = (lists[2], lists[3]) if len(lists) == 4 else None
        points.append((head[1], int(head[2]), int(head[3]), lists[0], lists[1], pay))
OFFSETS = [int(x) for x in (sys.argv[6].split(',') if len(sys.argv) > 6 else ['0'])]
capture = {}
for kind, t, op, r0, r1, pay in points:
    wires = set(r0) | set(r1) | (set(pay[0]) | set(pay[1]) if pay else set())
    for delta in OFFSETS:
        capture.setdefault(op + delta, set()).update(wires)
result = run(Path(ops), shots, seed, 10**9, (), False, capture)
pickle.dump({"points": points, "capture": capture, "failing": result["failing_inputs"], "shots": shots, "seed": seed},
            open(out, "wb"))
print("captured", len(capture), "points; correct", result["shots_correct"], "/", shots)
