"""Validate calculation rules and emit a scoped Toffoli saving ledger."""

import argparse
import itertools
import json
import math
import random
from pathlib import Path

from architecture.field_dag import affine_point_add
from architecture.provenance import Origin, RegionCompiler, ordered_depth
from architecture.quadratic import decompose, parity_product
from architecture.rewrites import gate, karatsuba_two_bit, rewrite_once
from architecture.verify import verify_region
from circuits.sparse_recycle import Quadratic, apply


def exact_basis_action(gates, bits):
    phase = 1
    for item in gates:
        kind, wires = item["kind"], item["wires"]
        if item.get("condition") is not None:
            raise ValueError("This exact unitary check has no classical condition model")
        if kind in ("X", "CX", "CCX"):
            if all(bits >> wire & 1 for wire in wires[:-1]):
                bits ^= 1 << wires[-1]
        elif kind in ("Z", "CZ"):
            if all(bits >> wire & 1 for wire in wires):
                phase = -phase
        else:
            raise ValueError(kind)
    return bits, phase


def verify_identity(before, after, qubits):
    for bits in range(1 << qubits):
        if exact_basis_action(before, bits) != exact_basis_action(after, bits):
            raise AssertionError(f"Basis/phase mismatch for input {bits}")
    rng = random.Random(qubits)
    state = [complex(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(1 << qubits)]
    norm = math.sqrt(sum(abs(value)**2 for value in state))
    left = [value / norm for value in state]
    right = left.copy()
    for program, vector in ((before, left), (after, right)):
        for item in program:
            apply(vector, (item["kind"], *item["wires"]))
    error = max(abs(a - b) for a, b in zip(left, right))
    if error > 1e-12:
        raise AssertionError("Coherent identity check failed")
    def resources(program):
        return {"toffolis": sum(item["kind"] == "CCX" for item in program),
                "cnot": sum(item["kind"] == "CX" for item in program),
                "ordered_toffoli_depth": ordered_depth(program, {"CCX"}), "declared_qubits": qubits}
    return {"exact_basis_states_checked": 1 << qubits, "coherent_max_error": error, "before": resources(before), "after": resources(after)}


def run_checks():
    fixtures = {
        "inverse_pair": ([gate("CCX", 0, 1, 2), gate("CCX", 1, 0, 2)], 3),
        "shared_control_factor": ([gate("CCX", 0, 1, 3), gate("CCX", 0, 2, 3)], 4),
        "shared_product_fanout": ([gate("CCX", 0, 1, 2), gate("CCX", 0, 1, 3)], 4),
        "phase_conjugation": ([gate("CCX", 0, 1, 2), gate("Z", 2), gate("CCX", 0, 1, 2)], 3),
    }
    results = {}
    for name, (before, qubits) in fixtures.items():
        after, certificates = rewrite_once(before)
        if len(certificates) != 1 or certificates[0]["rule"] != name:
            raise AssertionError("Unexpected rewrite certificate")
        results[name] = {**verify_identity(before, after, qubits), "certificate": certificates[0]}
    before, after = karatsuba_two_bit()
    results["two_bit_polynomial_karatsuba"] = verify_identity(before, after, 7)

    graph = affine_point_add()
    branches = cases = 0
    error = 0.0
    monomials = [0, 1, 2, 4, 3, 5, 6]
    for coefficient_mask in range(128):
        function = Quadratic(frozenset(term for index, term in enumerate(monomials) if coefficient_mask >> index & 1))
        compiler = RegionCompiler("quadratic.test", 4, 1, graph.nodes)
        lease = compiler.prepare_quadratic(function, Origin("slope", "quadratic rule verification fixture"))
        compiler.xor_into(lease, 3, compiler.stage)
        compiler.recycle(lease, compiler.stage)
        delta, count = verify_region(compiler.report(), [function], 4, coefficient_mask)
        error = max(error, delta)
        cases += 1
        branches += count
    rng = random.Random(850000)
    larger_terms = [0] + [1 << index for index in range(6)] + [(1 << i) | (1 << j) for i, j in itertools.combinations(range(6), 2)]
    for sample in range(16):
        function = Quadratic(frozenset(term for term in larger_terms if rng.random() < 0.4))
        compiler = RegionCompiler("quadratic.test6", 7, 1, graph.nodes)
        lease = compiler.prepare_quadratic(function, Origin("slope", "six-input quadratic fixture"))
        compiler.xor_into(lease, 6, compiler.stage)
        compiler.recycle(lease, compiler.stage)
        delta, count = verify_region(compiler.report(), [function], 7, sample)
        error = max(error, delta)
        cases += 1
        branches += count
    # Independent algebraic reconstruction for all 2,048 quadratic ANFs on
    # four inputs, including every affine residue and constant.
    reconstructed = 0
    monomials = [0] + [1 << index for index in range(4)] + [(1 << i) | (1 << j) for i, j in itertools.combinations(range(4), 2)]
    for coefficient_mask in range(1 << len(monomials)):
        function = Quadratic(frozenset(term for index, term in enumerate(monomials) if coefficient_mask >> index & 1))
        factors, residue = decompose(function)
        terms = set(residue)
        for left, right in factors:
            terms.symmetric_difference_update(parity_product(left, right))
        if terms != set(function.terms):
            raise AssertionError("Quadratic decomposition does not reconstruct the ANF")
        reconstructed += 1
    examples = {}
    for name, terms, data_qubits in (("majority_carry", {3, 5, 6}, 4), ("four_bit_quadratic_clique", {3, 5, 9, 6, 10, 12}, 5)):
        function = Quadratic(frozenset(terms))
        compiler = RegionCompiler("quadratic.example", data_qubits, 1, graph.nodes)
        lease = compiler.prepare_quadratic(function, Origin("slope", f"{name}: exact Boolean fixture"))
        compiler.xor_into(lease, data_qubits - 1, compiler.stage)
        compiler.recycle(lease, compiler.stage)
        delta, count = verify_region(compiler.report(), [function], data_qubits, 2026)
        error = max(error, delta)
        cases += 1
        branches += count
        examples[name] = {"direct_compute_toffolis": len(terms), "optimized_compute_toffolis": compiler.report()["logical_toffolis"], "cleanup_toffolis": 0, "peak_active": compiler.report()["peak_active"], "measurement_count": 1}
    results["quadratic_parity_factorization"] = {"coherent_cases": cases, "measurement_branches": branches, "max_statevector_error": error, "exact_anf_reconstructions": reconstructed, "examples": examples}
    if error > 1e-12:
        raise AssertionError("Quadratic coherent phase repair failed")
    return {"scope": "exact local rules and fixtures; no full secp256k1 improvement measured", "rules": results, "result": "pass"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(run_checks(), indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered)
    print(rendered, end="")
