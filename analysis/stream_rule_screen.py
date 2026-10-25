#!/usr/bin/env python3
"""Screen the local rewrite rules against a real ops.bin gate stream.

Reads the upstream QECCOPSZ format (zstd body, 56-byte records) through the
`zstd` CLI and counts, for every Toffoli-class gate, whether a partner inside
a commuting lookahead window would let one of the rules in
architecture/rewrites.py fire. Counts are static gates in the emitted
stream, split by whether the gate sits under a classical condition; they
are not the evaluator's average executed Toffolis.
"""

import argparse
import json
import struct
import subprocess
import sys
from collections import Counter, deque
from pathlib import Path

MAGIC = b"QECCOPSZ"
REC = struct.Struct("<II6Q")
NONE = (1 << 64) - 1
NAMES = ["NEG", "REGISTER", "APPEND", "BIT_INVERT", "BIT_STORE0", "BIT_STORE1", "X", "Z", "CX", "CZ",
         "SWAP", "R", "HMR", "CCX", "CCZ", "PUSH", "POP", "DEBUG"]
X_TYPE = {"X", "CX", "CCX"}
DIAGONAL = {"Z", "CZ", "CCZ"}
IGNORED = {"NEG", "REGISTER", "APPEND", "BIT_INVERT", "BIT_STORE0", "BIT_STORE1", "DEBUG"}


def records(path, limit=None):
    with open(path, "rb") as handle:
        header = handle.read(16)
    if header[:8] != MAGIC:
        raise SystemExit("bad magic")
    total = struct.unpack("<Q", header[8:])[0]
    tail = subprocess.Popen(["tail", "-c", "+17", str(path)], stdout=subprocess.PIPE)
    unz = subprocess.Popen(["zstd", "-dc", "--long=27"], stdin=tail.stdout, stdout=subprocess.PIPE)
    count = 0
    while limit is None or count < limit:
        chunk = unz.stdout.read(REC.size * 65536)
        if not chunk:
            break
        for kind, _, c2, c1, target, _, cond, _ in REC.iter_unpack(chunk):
            yield NAMES[kind], tuple(q for q in (c2, c1, target) if q != NONE), cond
            count += 1
    unz.kill()
    tail.kill()
    return total


def commute(a, b):
    """Exact for classical-reversible X-type and diagonal gates; else False."""
    ka, wa = a
    kb, wb = b
    if ka in X_TYPE and kb in X_TYPE:
        return wa[-1] not in wb[:-1] and wb[-1] not in wa[:-1]
    if ka in DIAGONAL and kb in DIAGONAL:
        return True
    if ka in X_TYPE and kb in DIAGONAL:
        return wa[-1] not in wb
    if ka in DIAGONAL and kb in X_TYPE:
        return wb[-1] not in wa
    return set(wa).isdisjoint(wb)


def match(first, second):
    (ka, wa), (kb, wb) = first, second
    if ka == "CCX" and kb == "CCX":
        ca, cb = set(wa[:2]), set(wb[:2])
        if wa[2] == wb[2] and ca == cb:
            return "inverse_pair", 2
        if ca == cb:
            return "shared_product_fanout", 1
        if wa[2] == wb[2] and len(ca & cb) == 1:
            return "shared_control_factor", 1
    if ka == "CCZ" and kb == "CCZ":
        sa, sb = set(wa), set(wb)
        if sa == sb:
            return "ccz_inverse_pair", 2
        if len(sa & sb) == 2:
            return "ccz_shared_pair", 1
    return None


def screen(path, window, limit):
    # Pending Toffoli-class gates that commute with every gate emitted after
    # them, so each could move forward to meet a matching later partner.
    pending = deque()
    stats = Counter()
    hits = Counter()
    stack = []
    ops = 0
    for kind, wires, cond in records(path, limit):
        ops += 1
        if kind in IGNORED:
            continue
        if kind == "PUSH":
            stack.append(cond)
            pending.clear()
            continue
        if kind == "POP":
            if stack:
                stack.pop()
            pending.clear()
            continue
        conditioned = bool(stack)
        gate = (kind, wires)
        if kind in ("CCX", "CCZ"):
            stats[f"{kind}_{'cond' if conditioned else 'uncond'}"] += 1
        partner = None
        if kind in ("CCX", "CCZ"):
            for index, (age, earlier) in enumerate(pending):
                found = match(earlier, gate)
                if found:
                    partner = index, found
                    break
        if partner:
            index, (rule, saved) = partner
            hits[(rule, "cond" if conditioned else "uncond")] += saved
            del pending[index]
            continue
        if kind not in X_TYPE | DIAGONAL:
            # SWAP/R/HMR: drop anything sharing a wire.
            pending = deque(item for item in pending if set(item[1][1]).isdisjoint(wires))
            continue
        pending = deque(item for item in pending if commute(item[1], gate) and ops - item[0] <= window)
        if kind in ("CCX", "CCZ"):
            pending.append((ops, gate))
    return {"ops_scanned": ops, "toffoli_class_static": dict(stats),
            "rule_hits_toffolis_saved_static": {f"{rule}/{cond}": n for (rule, cond), n in sorted(hits.items())},
            "window_ops": window,
            "scope": "static gates in the emitted stream; conditioned gates execute on a fraction of shots"}


def exact_repeats(path, limit=None):
    """Count CCX gates recomputing a product whose controls were not written since."""
    versions, live, measured, classes = Counter(), {}, {}, Counter()
    gaps, depth, measured_ccx, ccx = [], 0, 0, 0
    last_target = {}
    for index, (kind, wires, _) in enumerate(records(path, limit)):
        if kind in ("PUSH", "POP"):
            depth += 1 if kind == "PUSH" else -1
            continue
        if kind == "CCX":
            ccx += 1
            controls = frozenset(wires[:2])
            a, b = sorted(controls)
            previous = live.get(controls)
            if previous and previous[2:] == (versions[a], versions[b]):
                when = measured.get(previous[1])
                if when is not None and when > previous[0]:
                    classes["measured_then_recomputed"] += 1
                    gaps.append(index - previous[0])
                else:
                    classes["first_target_live_or_rewritten"] += 1
                classes["conditioned" if depth else "unconditioned"] += 1
            live[controls] = (index, wires[2], versions[a], versions[b])
            last_target[wires[2]] = index
        if kind in X_TYPE:
            versions[wires[-1]] += 1
        elif kind == "SWAP":
            versions[wires[0]] += 1
            versions[wires[1]] += 1
        elif kind in ("R", "HMR"):
            versions[wires[-1]] += 1
            measured[wires[-1]] = index
            if kind == "HMR" and last_target.pop(wires[-1], None) is not None:
                measured_ccx += 1
    gaps.sort()
    return {"ccx": ccx, "identical_product_repeats": dict(classes),
            "recompute_gap_ops_min_median_max": [gaps[0], gaps[len(gaps) // 2], gaps[-1]] if gaps else None,
            "ccx_targets_cleaned_by_hmr": measured_ccx}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ops", type=Path)
    parser.add_argument("--window", type=int, default=256)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = screen(args.ops, args.window, args.limit)
    result["exact_repeats"] = exact_repeats(args.ops, args.limit)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered)
    sys.stdout.write(rendered)
