#!/usr/bin/env python3
"""Prove or refute stream-bound Toffoli cuts by sound symbolic dataflow.

Each qubit carries an abstract term: ZERO, an opaque atom (a value we do
not model), or AND(set of atoms). Equal terms denote equal values on
*every* input, so a cut whose side condition holds on terms is proved;
anything else is "unproved" (it may still be true, but only on inputs).
Conditional writes, X, and any write we cannot model produce fresh atoms,
which only makes the analysis more conservative.

Cut types (upstream lane3_sigcut format: i n z, then 7-field records):
  HMR t           -> SWAP t,p ; BIT_STORE0     park: needs p = ZERO
  CCX a,b,t       -> SWAP p,t                  unpark: needs p = AND(a,b), t = ZERO
  CCX a,b,t       -> CX c,t                    needs c = AND(a,b)
  CCX a,b,t       -> (nothing)                 needs AND(a,b) = ZERO
"""

import argparse
import itertools
import json
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path

NONE = (1 << 64) - 1
REC = struct.Struct("<II6Q")
NAMES = ["NEG", "REG", "APP", "BINV", "B0", "B1", "X", "Z", "CX", "CZ", "SWAP", "R", "HMR", "CCX", "CCZ", "PUSH", "POP", "DBG"]
ZERO = frozenset()
ONE = frozenset({frozenset()})


def stream(path):
    tail = subprocess.Popen(["tail", "-c", "+17", str(path)], stdout=subprocess.PIPE)
    unz = subprocess.Popen(["zstd", "-dc", "--long=27"], stdin=tail.stdout, stdout=subprocess.PIPE)
    while chunk := unz.stdout.read(REC.size * 65536):
        for kind, _, c2, c1, t, cb, cc, r in REC.iter_unpack(chunk):
            yield (kind, c2, c1, t, cb, cc, r)


def load_cuts(path):
    lines = Path(path).read_text().splitlines()
    length = int(lines[0].split()[0])
    cuts = []
    for line in lines[1:]:
        a = list(map(int, line.split()))
        i, n, z = a[:3]
        old = [tuple(a[3 + 7 * j:10 + 7 * j]) for j in range(n)]
        new = [tuple(a[3 + 7 * (n + j):10 + 7 * (n + j)]) for j in range(z)]
        cuts.append((i, old, new))
    return length, cuts


class Terms:
    """Bounded ANF over opaque atoms: a term is a frozenset of monomials,
    each monomial a frozenset of atom ids (empty = constant 1). Terms
    larger than CAP monomials are replaced by a fresh atom (sound)."""
    CAP = 64

    def __init__(self):
        self.value = {}
        self.fresh = itertools.count(1)

    def get(self, q):
        return self.value.get(q, ZERO)

    def atom(self):
        return frozenset({frozenset({next(self.fresh)})})

    def cap(self, term):
        return term if len(term) <= self.CAP else self.atom()

    def conj(self, a, b):
        out = set()
        for x in a:
            for y in b:
                out ^= {x | y}
        return self.cap(frozenset(out))

    def apply(self, op, conditioned):
        kind, c2, c1, t, *_ = op
        name = NAMES[kind]
        if name == "SWAP":
            if conditioned:
                self.value[c1], self.value[t] = self.atom(), self.atom()
            else:
                self.value[c1], self.value[t] = self.get(t), self.get(c1)
        elif name in ("R", "HMR"):
            self.value[t] = self.atom() if conditioned else ZERO
        elif name in ("X", "CX", "CCX"):
            if conditioned:
                self.value[t] = self.atom()
                return
            source = ONE if name == "X" else self.get(c1) if name == "CX" else self.conj(self.get(c1), self.get(c2))
            self.value[t] = self.cap(self.get(t) ^ source)


def check(cut, terms):
    i, old, new = cut
    kinds = ([NAMES[o[0]] for o in old], [NAMES[o[0]] for o in new])
    o = old[0]
    if kinds == (["HMR"], ["SWAP", "B0"]):
        p = new[0][3] if new[0][2] == o[3] else new[0][2]
        return "park", terms.get(p) == ZERO
    product = terms.conj(terms.get(o[2]), terms.get(o[1])) if kinds[0] == ["CCX"] else None
    if kinds == (["CCX"], ["SWAP"]):
        s = new[0]
        p = s[2] if s[3] == o[3] else s[3]
        return "unpark", terms.get(p) == product and terms.get(o[3]) == ZERO
    if kinds == (["CCX"], ["CX"]):
        return "ccx_to_cx", terms.get(new[0][2]) == product
    if kinds == (["CCX"], []):
        return "ccx_delete", product == ZERO
    return "other", False


def main(ops, cuts_path, report):
    length, cuts = load_cuts(cuts_path)
    pending = {cut[0]: cut for cut in cuts}
    terms, depth, results = Terms(), 0, Counter()
    unproved = []
    for index, op in enumerate(stream(ops)):
        if index >= length:
            break
        if index in pending:
            cut = pending[index]
            kind, ok = check(cut, terms)
            results[kind, ok, depth > 0] += 1
            if not ok:
                unproved.append(index)
            for new in cut[2]:
                terms.apply(new, depth > 0)
            continue
        name = NAMES[op[0]]
        if name == "PUSH":
            depth += 1
        elif name == "POP":
            depth -= 1
        else:
            terms.apply(op, depth > 0)
    # Cuts with multi-op originals would need skipping; all rows here are single-op.
    summary = {f"{k}/{'proved' if ok else 'unproved'}/{'conditioned' if c else 'unconditioned'}": v
               for (k, ok, c), v in sorted(results.items())}
    out = {"cuts": len(cuts), "results": summary, "unproved_positions": unproved,
           "method": "sound bounded-ANF dataflow over opaque atoms (cap 64 monomials); unproved = not derivable, not necessarily false"}
    if report:
        Path(report).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "unproved_positions"}, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ops", type=Path, help="stream *before* the cuts (e.g. a build with lane3_sigcut disabled)")
    parser.add_argument("cuts", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    main(args.ops, args.cuts, args.report)
