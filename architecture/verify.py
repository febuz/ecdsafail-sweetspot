"""Coherent branch checks for emitted bilinear gates and phase repairs."""

import argparse
import json
import math
import random
from pathlib import Path

from architecture.bilinear import factor, monomials
from architecture.demo import demonstration
from architecture.field_dag import affine_point_add
from architecture.provenance import Origin, RegionCompiler
from circuits.sparse_recycle import Quadratic, apply


def verify_region(report, functions, data_qubits, seed=1):
    rng = random.Random(seed)
    size = 1 << data_qubits
    initial = [complex(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(size)]
    norm = math.sqrt(sum(abs(value)**2 for value in initial))
    initial = [value / norm for value in initial]
    qubits = max([data_qubits - 1] + [wire for gate in report["gates"] for wire in gate["wires"]]) + 1
    expected = [0j] * (1 << qubits)
    output = data_qubits - 1
    for index, value in enumerate(initial):
        flip = sum(function.evaluate(index) for function in functions) % 2
        expected[index ^ (flip << output)] = value
    worst = 0.0
    branches = 1 << report["measurement_count"]
    for coins in range(branches):
        state = [0j] * (1 << qubits)
        state[:size] = initial
        outcomes = {}
        measurement_index = 0
        for gate in report["gates"]:
            if gate["condition"] is not None and not outcomes[gate["condition"]]:
                continue
            if gate["kind"] == "HMR":
                wire = gate["wires"][0]
                apply(state, ("H", wire))
                coin = coins >> measurement_index & 1
                measurement_index += 1
                probability = sum(abs(value)**2 for index, value in enumerate(state) if index >> wire & 1 == coin)
                if abs(probability - 0.5) > 1e-12:
                    raise AssertionError("Expected a uniform X-measurement branch")
                state = [value / math.sqrt(probability) if index >> wire & 1 == coin else 0j for index, value in enumerate(state)]
                if coin:
                    apply(state, ("X", wire))
                outcomes[gate["measurement_output"]] = coin
            elif gate["kind"] == "NEG":
                state = [-value for value in state]
            else:
                apply(state, (gate["kind"], *gate["wires"]))
        worst = max(worst, max(abs(left - right) for left, right in zip(state, expected)))
    return worst, branches


def run_checks():
    max_error, coherent_cases, branches = 0.0, 0, 0
    graph = affine_point_add()
    # Every 2x3 binary matrix: compare the actual emitted reversible gates,
    # X measurements, conditional repairs, and resets with the ideal reader.
    for bits in range(64):
        matrix = [[bits >> (3*i + j) & 1 for j in range(3)] for i in range(2)]
        compiler = RegionCompiler("multiply.test", 6, 1, graph.nodes)
        lease = compiler.prepare_bilinear(matrix, (0, 1), (2, 3, 4), Origin("slope", "test bilinear 2x3 partial-product matrix"))
        compiler.xor_into(lease, 5, compiler.stage)
        compiler.recycle(lease, compiler.stage)
        error, count = verify_region(compiler.report(), [Quadratic(monomials(matrix, (0, 1), (2, 3, 4)))], 6, bits)
        max_error = max(max_error, error)
        coherent_cases += 1
        branches += count
    # The two-lease demo uses the same scratch wire twice, with a useful
    # coherent reader before each measurement.
    demo = demonstration()["scratch_region"]
    functions = [Quadratic(frozenset({5, 9, 6, 10})), Quadratic(frozenset({9}))]
    error, count = verify_region(demo, functions, 5, 2026)
    max_error = max(max_error, error)
    coherent_cases += 1
    branches += count
    # Exhaustive reconstruction proves the decomposition, independently of
    # the gate simulator, on every 3x3 binary matrix.
    reconstructed = 0
    for bits in range(512):
        matrix = [[bits >> (3*i + j) & 1 for j in range(3)] for i in range(3)]
        factors = factor(matrix)
        for i in range(3):
            for j in range(3):
                if sum((u >> i & 1) * (v >> j & 1) for u, v in factors) % 2 != matrix[i][j]:
                    raise AssertionError("Incorrect GF(2) matrix reconstruction")
        reconstructed += 1
    if max_error > 1e-12:
        raise AssertionError(f"Coherent gate mismatch: {max_error}")
    return {
        "scope": "bilinear compiler and stage-local recycling only; no complete ECDSA circuit",
        "coherent_cases": coherent_cases,
        "measurement_branches": branches,
        "exhaustive_3x3_matrix_reconstructions": reconstructed,
        "max_statevector_error": max_error,
        "demo_direct_partial_product_compute_toffolis": demo["bilinear_rank_lowering"]["direct_partial_product_toffolis"],
        "demo_factored_compute_toffolis": demo["logical_toffolis"],
        "demo_measured_cleanup_toffolis": 0,
        "demo_peak_active": demo["peak_active"],
        "demo_classical_outcome_bits": demo["measurement_count"],
        "result": "pass",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(run_checks(), indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered)
    print(rendered, end="")
