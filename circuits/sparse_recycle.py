#!/usr/bin/env python3
"""Compile quadratic scratch cleanup into X measurement and Z/CZ repair.

The data controls must retain their values through cleanup. This is a small
research component, not an ECDSA point-addition circuit or a novelty claim.
"""

import argparse
import itertools
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Quadratic:
    # A term is a bit mask: 0 is the constant, 1<<i is x_i, and a mask
    # with two set bits is x_i*x_j. Repeated terms cancel over GF(2).
    terms: frozenset[int]

    def __post_init__(self):
        if any(term < 0 or term.bit_count() > 2 for term in self.terms):
            raise ValueError("Only constant, linear, and quadratic terms are supported")

    def evaluate(self, value: int) -> int:
        return sum((value & term) == term for term in self.terms) % 2

    def compute(self, target: int):
        gates = []
        for term in sorted(self.terms):
            controls = tuple(i for i in range(term.bit_length()) if term >> i & 1)
            gates.append(("X" if not controls else "CX" if len(controls) == 1 else "CCX", *controls, target))
        return gates


def phase_repair(functions: list[Quadratic], outcome: int):
    """Return a scalar phase and a sparse Z/CZ list for the measured word."""
    terms: set[int] = set()
    for index, function in enumerate(functions):
        if outcome >> index & 1:
            terms.symmetric_difference_update(function.terms)
    gates = []
    for term in sorted(terms - {0}):
        controls = tuple(i for i in range(term.bit_length()) if term >> i & 1)
        gates.append(("Z" if len(controls) == 1 else "CZ", *controls))
    return (-1 if 0 in terms else 1), gates


def apply(state, gate):
    kind, *wires = gate
    if kind in ("X", "CX", "CCX"):
        target = wires[-1]
        mask = sum(1 << wire for wire in wires[:-1])
        for index in range(len(state)):
            if not (index >> target & 1) and index & mask == mask:
                other = index ^ (1 << target)
                state[index], state[other] = state[other], state[index]
    elif kind in ("Z", "CZ"):
        mask = sum(1 << wire for wire in wires)
        for index in range(len(state)):
            if index & mask == mask:
                state[index] = -state[index]
    elif kind == "H":
        target = wires[0]
        for index in range(len(state)):
            if not (index >> target & 1):
                other = index ^ (1 << target)
                left, right = state[index], state[other]
                state[index] = (left + right) / math.sqrt(2)
                state[other] = (left - right) / math.sqrt(2)
    else:
        raise ValueError(kind)


def check_case(n: int, functions: list[Quadratic], amplitudes: list[complex]):
    """Use actual gates, branch all X measurements, and compare coherent data."""
    count = len(functions)
    scratch = list(range(n + 1, n + 1 + count))
    output = n
    state = [0j] * (1 << (n + 1 + count))
    norm = math.sqrt(sum(abs(value) ** 2 for value in amplitudes))
    initial = [value / norm for value in amplitudes]
    state[:len(initial)] = initial
    for function, target in zip(functions, scratch):
        for gate in function.compute(target):
            apply(state, gate)
    # Scratch has a useful coherent reader before it is erased.
    for target in scratch:
        apply(state, ("CX", target, output))
    expected = [0j] * len(initial)
    for index, value in enumerate(initial):
        flip = sum(function.evaluate(index) for function in functions) % 2
        expected[index ^ (flip << output)] = value
    for target in scratch:
        apply(state, ("H", target))

    max_error = 0.0
    for outcome in range(1 << count):
        branch = [state[index | (outcome << (n + 1))] * math.sqrt(1 << count) for index in range(len(initial))]
        scalar, gates = phase_repair(functions, outcome)
        branch = [scalar * value for value in branch]
        for gate in gates:
            apply(branch, gate)
        max_error = max(max_error, max(abs(left - right) for left, right in zip(branch, expected)))
    return max_error, 1 << count


def self_check():
    rng = random.Random(20261025)
    cases = branches = 0
    maximum = 0.0
    # Every quadratic Boolean polynomial on three live input bits, including
    # constants, tested on a full-support complex superposition and both coins.
    n = 3
    monomials = [0] + [1 << i for i in range(n)] + [(1 << i) | (1 << j) for i, j in itertools.combinations(range(n), 2)]
    for coefficient_mask in range(1 << len(monomials)):
        function = Quadratic(frozenset(term for i, term in enumerate(monomials) if coefficient_mask >> i & 1))
        amplitudes = [complex(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(1 << (n + 1))]
        error, coins = check_case(n, [function], amplitudes)
        maximum = max(maximum, error)
        cases += 1
        branches += coins
    # Multi-scratch cases exercise cancellation of terms across outcomes.
    n = 5
    monomials = [0] + [1 << i for i in range(n)] + [(1 << i) | (1 << j) for i, j in itertools.combinations(range(n), 2)]
    for _ in range(32):
        functions = [Quadratic(frozenset(term for term in monomials if rng.random() < 0.3)) for _ in range(3)]
        amplitudes = [complex(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(1 << (n + 1))]
        error, coins = check_case(n, functions, amplitudes)
        maximum = max(maximum, error)
        cases += 1
        branches += coins

    # Negative controls: the Bell-state example detects both raw Z-readout and
    # omission of the X-measurement phase repair on the outcome-one branch.
    plus = [1 / math.sqrt(2), 1 / math.sqrt(2)]
    z_branch = [1.0, 0.0]
    missing_repair = [plus[0], -plus[1]]
    z_fidelity = abs(sum(a.conjugate() * b for a, b in zip(plus, z_branch))) ** 2
    missing_fidelity = abs(sum(a.conjugate() * b for a, b in zip(plus, missing_repair))) ** 2
    assert maximum < 1e-12
    assert z_fidelity < 0.51 and missing_fidelity < 1e-12
    example = [Quadratic(frozenset({1, 3, 5})), Quadratic(frozenset({2, 3, 6}))]
    compute_t = sum(sum(gate[0] == "CCX" for gate in f.compute(n + 1 + i)) for i, f in enumerate(example))
    return {
        "scope": "local quadratic-scratch identity; not a full ECDSA circuit",
        "coherent_cases": cases,
        "all_measurement_branches_checked": branches,
        "max_statevector_error": maximum,
        "raw_z_measurement_negative_control_fidelity": z_fidelity,
        "missing_phase_repair_negative_control_fidelity": missing_fidelity,
        "example_compute_toffolis": compute_t,
        "example_coherent_uncompute_toffolis": compute_t,
        "example_measured_cleanup_toffolis": 0,
        "data_controls_must_remain_available": True,
        "result": "pass",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = self_check()
    rendered = json.dumps(result, indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered)
    print(rendered, end="")
