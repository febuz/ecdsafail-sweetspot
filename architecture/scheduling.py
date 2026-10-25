"""Conservative commutation, reuse exposure, and disjoint-wire scheduling.

Only small unconditional unitary windows are supported. Measurements,
classical conditions, unknown gates, and stage changes are barriers.
"""

from copy import deepcopy

from architecture.rewrites import rewrite_once


X_TYPES = {"X", "CX", "CCX"}
PHASE_TYPES = {"Z", "CZ"}


def commute(first, second):
    if first.get("condition") is not None or second.get("condition") is not None or first.get("stage") != second.get("stage"):
        return False
    a, b = first["kind"], second["kind"]
    if a not in X_TYPES | PHASE_TYPES or b not in X_TYPES | PHASE_TYPES:
        return False
    left, right = first["wires"], second["wires"]
    if a in X_TYPES and b in X_TYPES:
        return left[-1] not in right[:-1] and right[-1] not in left[:-1]
    if a in PHASE_TYPES and b in PHASE_TYPES:
        return True
    if a in X_TYPES:
        return left[-1] not in right
    return right[-1] not in left


def expose_reuse(gates, lookahead=32):
    if len(gates) > 512:
        raise ValueError("Split the program into verified windows of at most 512 gates")
    program = deepcopy(gates)
    for index, item in enumerate(program):
        item.setdefault("id", index)
        item.setdefault("lineage", [item["id"]])
    moves, rewrites = [], []
    while True:
        change = None
        for first in range(len(program)):
            if program[first]["kind"] != "CCX":
                continue
            for last in range(first + 1, min(len(program), first + lookahead + 1)):
                _, certificates = rewrite_once([program[first], program[last]])
                if certificates and all(commute(program[last], item) for item in program[first + 1:last]):
                    change = first, last
                    break
            if change:
                break
        if change is None:
            break
        first, last = change
        moves.append({"moved_source_gate_ids": program[last]["lineage"],
                      "crossed_source_gate_ids": [item["lineage"] for item in program[first + 1:last]],
                      "proof_condition": "moved gate commutes exactly with every crossed gate"})
        program = program[:first + 1] + [program[last]] + program[first + 1:last] + program[last + 1:]
        program, certificates = rewrite_once(program)
        if not certificates:
            raise AssertionError("A reuse exposure must lower Toffoli count")
        rewrites.extend(certificates)
    return {"gates": program, "commutation_moves": moves, "rewrite_certificates": rewrites,
            "scope": "local unconditional unitary window; no measurement reordering"}


def parallel_schedule(gates):
    """Return one achieved schedule; no optimal-depth claim or free fanout."""
    if len(gates) > 512:
        raise ValueError("Use a small verified unitary window")
    if any(item.get("condition") is not None or item["kind"] not in X_TYPES | PHASE_TYPES for item in gates):
        raise ValueError("Only unconditional X/CX/CCX/Z/CZ gates can be scheduled")
    if len({item.get("stage") for item in gates}) > 1:
        raise ValueError("Stage boundaries must be preserved")
    predecessors = {index: {previous for previous in range(index) if not commute(gates[previous], gate)} for index, gate in enumerate(gates)}
    remaining, done, layers = set(range(len(gates))), set(), []
    while remaining:
        ready = sorted(index for index in remaining if predecessors[index] <= done)
        # Prepare all available Clifford work before a Toffoli batch. This
        # aligns independent non-Clifford gates without adding control copies.
        # It is a depth heuristic, not a physical-time or optimality claim.
        cliffords = [index for index in ready if gates[index]["kind"] != "CCX"]
        if cliffords:
            ready = cliffords
        busy, layer = set(), []
        for index in ready:
            if busy.isdisjoint(gates[index]["wires"]):
                layer.append(index)
                busy.update(gates[index]["wires"])
        if not layer:
            raise AssertionError("Dependency cycle")
        done.update(layer)
        remaining.difference_update(layer)
        layers.append(layer)
    return {"layers": layers,
            "gates": [deepcopy(gates[index]) for layer in layers for index in layer],
            "abstract_gate_layers": len(layers),
            "toffoli_containing_layers": sum(any(gates[index]["kind"] == "CCX" for index in layer) for layer in layers),
            "extra_qubits": 0,
            "scope": "achieved disjoint-wire schedule; no optimality, physical timing, or free control copying"}
