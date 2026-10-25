#!/usr/bin/env python3
"""Measure value-occupied width of an ops.bin by bit-parallel classical simulation.

The evaluator scores width as (max wire index + 1). A wire that holds |0> on
every simulated shot can be relabelled freely, so the maximum number of
simultaneously non-zero wires is the width a pure wire-renaming pass
(interval colouring of non-zero segments) could reach without changing a
single gate. Inputs are valid secp256k1 points generated like the
evaluator's; HMR/R outcomes are random as in the evaluator. Phase is not
tracked: it does not affect which wires are non-zero.
"""

import argparse
import json
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stream_rule_screen import NONE, REC, MAGIC  # noqa: E402

import subprocess

P = 2**256 - 2**32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0]:
        if (a[1] + b[1]) % P == 0:
            return None
        lam = 3 * a[0] * a[0] * pow(2 * a[1], -1, P) % P
    else:
        lam = (b[1] - a[1]) * pow(b[0] - a[0], -1, P) % P
    x = (lam * lam - a[0] - b[0]) % P
    return x, (lam * (a[0] - x) - a[1]) % P


def mul(k, point=G):
    result = None
    while k:
        if k & 1:
            result = add(result, point)
        point = add(point, point)
        k >>= 1
    return result


def raw_ops(path):
    with open(path, "rb") as handle:
        if handle.read(8) != MAGIC:
            raise SystemExit("bad magic")
    tail = subprocess.Popen(["tail", "-c", "+17", str(path)], stdout=subprocess.PIPE)
    unz = subprocess.Popen(["zstd", "-dc", "--long=27"], stdin=tail.stdout, stdout=subprocess.PIPE)
    while chunk := unz.stdout.read(REC.size * 65536):
        yield from REC.iter_unpack(chunk)


def fiat_shamir_inputs(path, count=9024):
    """The evaluator's own test points: SHAKE256 over the op stream (v2 domain)."""
    import hashlib
    with open(path, "rb") as handle:
        total = struct.unpack("<Q", handle.read(16)[8:])[0]
    hasher = hashlib.shake_256(b"quantum_ecc-fiat-shamir-v2" + struct.pack("<Q", total))
    batch = []
    for kind, _, c2, c1, target, bit, cbit, reg in raw_ops(path):
        batch.append(struct.pack("<B6Q", kind, c2, c1, target, bit, cbit, reg))
        if len(batch) == 65536:
            hasher.update(b"".join(batch))
            batch = []
    hasher.update(b"".join(batch))
    stream = hasher.digest(64 * count)
    points = []
    for shot in range(count):
        k1 = int.from_bytes(stream[64 * shot:64 * shot + 32], "little")
        k2 = int.from_bytes(stream[64 * shot + 32:64 * shot + 64], "little")
        t, o = mul(k1), mul(k2)
        if t is None or o is None or t[0] == o[0]:
            continue
        points.append((t, o))
    return points


def registers(path):
    # Upstream circuits may declare registers anywhere (the leader does it last).
    regs = {}
    for kind, _, _, _, target, bit, _, reg in raw_ops(path):
        if kind == 2:
            regs.setdefault(reg, []).append(("q", target) if target != NONE else ("b", bit))
    return regs


def affine_rank(vectors, full):
    """GF(2) rank of wire-value vectors over shots, with the all-ones constant."""
    pivots = {}
    rank = 0
    for vector in [full, *vectors]:
        for bit in sorted(pivots, reverse=True):
            if vector >> bit & 1:
                vector ^= pivots[bit]
        if vector:
            pivots[vector.bit_length() - 1] = vector
            rank += 1
    return rank - 1


def ranges(indices):
    out = []
    for index in indices:
        if out and index == out[-1][1] + 1:
            out[-1][1] = index
        else:
            out.append([index, index])
    return out


def run(path, shots, seed, sample_every, rank_points=(), fiat_shamir=False):
    rng = random.Random(seed)
    regs = registers(path)
    fixed = fiat_shamir_inputs(path) if fiat_shamir else None
    if fixed:
        shots = len(fixed)
    full = (1 << shots) - 1
    q, bits = {}, {}
    expected = []
    for shot in range(shots):
        while not fixed:
            t, o = mul(rng.randrange(1, N)), mul(rng.randrange(1, N))
            if t[0] != o[0]:
                break
        if fixed:
            t, o = fixed[shot]
        expected.append(add(t, o))
        for reg, value in zip(range(4), (t[0], t[1], o[0], o[1])):
            for index, (kind, wire) in enumerate(regs[reg]):
                if value >> index & 1:
                    store = q if kind == "q" else bits
                    store[wire] = store.get(wire, 0) | 1 << shot
    nonzero = {wire for wire, value in q.items() if value}
    peak, peak_op, trace = len(nonzero), 0, []
    start = {wire: 0 for wire in nonzero}
    segments_at_peak = None
    last_touch = {}
    cond, stack = full, []
    max_wire = 0
    ranks, snapshots = {}, {}
    classes = {}
    def key(value):
        return min(value, value ^ full)
    for wire in nonzero:
        classes[key(q[wire])] = classes.get(key(q[wire]), 0) + 1
    distinct_peak, distinct_peak_op = len(classes), 0
    distinct_hist, band_ops, distinct_band = {}, [], 1222
    for index, (kind, _, c2, c1, target, bit, cbit, _) in enumerate(raw_ops(path)):
        if kind == 15:
            stack.append(cond)
            cond &= bits.get(cbit, 0)
            continue
        if kind == 16:
            cond = stack.pop() if stack else full
            continue
        touched = ()
        if kind in (6, 8, 13, 11, 12):
            before = (q.get(target, 0),)
        elif kind == 10:
            before = (q.get(c1, 0), q.get(target, 0))
        else:
            before = ()
        if kind == 13:
            q[target] = q.get(target, 0) ^ (cond & q.get(c1, 0) & q.get(c2, 0))
            touched = (target,)
            last_touch[c1] = last_touch[c2] = index
        elif kind == 8:
            q[target] = q.get(target, 0) ^ (cond & q.get(c1, 0))
            touched = (target,)
            last_touch[c1] = index
        elif kind == 6:
            q[target] = q.get(target, 0) ^ cond
            touched = (target,)
        elif kind == 10:
            a, b = q.get(c1, 0), q.get(target, 0)
            diff = (a ^ b) & cond
            q[c1], q[target] = a ^ diff, b ^ diff
            touched = (c1, target)
        elif kind in (11, 12):
            if kind == 12:
                outcome = rng.getrandbits(shots)
                bits[bit] = (bits.get(bit, 0) & ~cond) ^ (outcome & cond)
            q[target] = q.get(target, 0) & ~cond
            touched = (target,)
        elif kind == 3:
            bits[bit] = bits.get(bit, 0) ^ cond
        elif kind == 4:
            bits[bit] = bits.get(bit, 0) & ~cond
        elif kind == 5:
            bits[bit] = bits.get(bit, 0) | cond
        elif kind in (7, 9, 14):
            for wire in (c2, c1, target):
                if wire != NONE:
                    last_touch[wire] = index
        for wire, old in zip(touched, before):
            if old:
                k = key(old)
                classes[k] -= 1
                if not classes[k]:
                    del classes[k]
            if q[wire]:
                k = key(q[wire])
                classes[k] = classes.get(k, 0) + 1
        if len(classes) >= 1200:
            distinct_hist[len(classes)] = distinct_hist.get(len(classes), 0) + 1
            if len(classes) >= distinct_band:
                band_ops.append(index)
        if len(classes) > distinct_peak:
            distinct_peak, distinct_peak_op = len(classes), index
        for wire in touched:
            max_wire = max(max_wire, wire)
            last_touch[wire] = index
            if q[wire]:
                if wire not in nonzero:
                    nonzero.add(wire)
                    start[wire] = index
            elif wire in nonzero:
                nonzero.discard(wire)
        if len(nonzero) > peak:
            peak, peak_op = len(nonzero), index
            segments_at_peak = {wire: (start[wire], last_touch.get(wire, start[wire])) for wire in nonzero}
        if index % sample_every == 0:
            trace.append((index, len(nonzero)))
        if index in rank_points:
            live = [q[wire] for wire in nonzero]
            ranks[index] = {"live": len(live), "affine_rank": affine_rank(live, full)}
            snapshots[index] = {"values": {wire: q[wire] for wire in nonzero},
                                "last_touch": {wire: last_touch.get(wire, -1) for wire in nonzero}}
    def read(reg, shot):
        return sum(((q if kind == "q" else bits).get(wire, 0) >> shot & 1) << index
                   for index, (kind, wire) in enumerate(regs[reg]))
    correct = sum((read(0, shot), read(1, shot)) == expected[shot] for shot in range(shots))
    idle = sorted(peak_op - touch for _, touch in segments_at_peak.values())
    buckets = {f"idle_ge_{limit}": sum(gap >= limit for gap in idle) for limit in (1_000, 10_000, 100_000, 1_000_000)}
    return {"shots": shots, "shots_correct": correct, "nonzero_wires_at_end": len(nonzero), "declared_width": max_wire + 1, "peak_nonzero_wires": peak, "peak_op": peak_op,
            "renaming_slack": max_wire + 1 - peak,
            "peak_distinct_values": distinct_peak, "peak_distinct_op": distinct_peak_op,
            "copy_elimination_ceiling": max_wire + 1 - distinct_peak,
            "ops_by_distinct_count_ge_1200": dict(sorted(distinct_hist.items())),
            "ops_with_distinct_ge_1222_ranges": ranges(band_ops),
            "live_at_peak_idle_since_last_touch": buckets,
            "linear_dependency_at": ranks,
            "trace_every": sample_every, "trace": trace,
            "snapshots": snapshots,
            "scope": "classical shot sample; a wire zero on all sampled shots may still be non-zero on rare inputs"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ops", type=Path)
    parser.add_argument("--shots", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1080)
    parser.add_argument("--sample-every", type=int, default=20000)
    parser.add_argument("--fiat-shamir", action="store_true", help="use the evaluator's own 9,024 test points")
    parser.add_argument("--rank-at", type=int, nargs="*", default=[])
    parser.add_argument("--snapshots", type=Path, help="pickle of live wire values at --rank-at ops")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = run(args.ops, args.shots, args.seed, args.sample_every, set(args.rank_at), args.fiat_shamir)
    snapshots = result.pop("snapshots")
    if args.snapshots:
        import pickle
        args.snapshots.write_bytes(pickle.dumps(snapshots))
    if args.report:
        args.report.write_text(json.dumps(result) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "trace"}, indent=2))
