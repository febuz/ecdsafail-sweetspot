#!/usr/bin/env python3
"""Find the first tick where P_i = c * lambda * R_i (mod p) breaks for failing shots.

Rails are two's complement LSB-first on the traced wires; with LF_LOWREL the
bit-0 wire is dropped (rails are odd), so both decodings are tried and the
one under which passing shots satisfy a fixed-ratio invariant is used.
"""
import pickle
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from localize_failures import inputs  # noqa: E402

P = 2**256 - 2**32 - 977


def value(capture, wires, shot, signed=True, odd=False):
    v = sum((capture[w] >> shot & 1) << i for i, w in enumerate(wires))
    if signed and wires and v >> (len(wires) - 1) & 1:
        v -= 1 << len(wires)
    return (v << 1) | 1 if odd else v


d = pickle.load(open(sys.argv[1], "rb"))
pts = d["points"]
seed, shots = d["seed"], d["shots"]
pts_in = inputs(seed, shots)
failing = {tuple(f["target"]) for f in d["failing"]}
fail = [i for i, (t, _) in enumerate(pts_in) if tuple(t) in failing]
passing = [i for i in range(shots) if i not in set(fail)][:48]
lam = [(t[1] - o[1]) * pow(t[0] - o[0], -1, P) % P for t, o in pts_in]


def ratios(cap, r, pay, shot, odd):
    out = []
    for rail, pw in ((r[0], pay[0]), (r[1], pay[1])):
        R = value(cap, rail, shot, True, odd) % P
        Pv = value(cap, pw, shot, False) % P
        if R == 0:
            return None
        out.append(Pv * pow(R, -1, P) * pow(lam[shot], -1, P) % P)
    return out


for leg_name, kind in (("divide", "fwd"),):
    cand = [(k, t, op, r0, r1, pay) for k, t, op, r0, r1, pay in pts if k == kind and pay is not None and op < 5_000_000]
    # choose decoding on passing shots: ratio constant across shots at a given tick
    best = None
    for odd in (False, True):
        k, t, op, r0, r1, pay = cand[len(cand) // 2]
        cap = d["capture"][op]
        rs = {tuple(ratios(cap, (r0, r1), pay, s, odd) or ()) for s in passing}
        if len(rs) <= 2:
            best = odd
    print(leg_name, "decoding odd-implicit:", best)
    first_bad = Counter()
    for s in fail:
        bad_at = None
        for k, t, op, r0, r1, pay in cand:
            cap = d["capture"][op]
            ref = {tuple(ratios(cap, (r0, r1), pay, q, best) or ()) for q in passing[:8]}
            mine = tuple(ratios(cap, (r0, r1), pay, s, best) or ())
            if mine not in ref:
                bad_at = t
                break
        first_bad[bad_at] += 1
        print(f"  failing shot {s}: first tick violating P = c*lambda*R : {bad_at}")
