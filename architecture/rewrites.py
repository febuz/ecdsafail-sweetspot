"""Exact local Clifford/Toffoli identities with source provenance.

These rules preserve arbitrary target states. The matcher refuses stage
boundaries and classical conditions; measurement boundaries are barriers.
"""

from copy import deepcopy


def gate(kind, *wires, field_node="fixture", stage="rulebook"):
    return {"kind": kind, "wires": list(wires), "condition": None,
            "stage": stage, "origin": {"field_node": field_node, "expansion": "local rule fixture"}}


def ccx(item):
    return item["kind"] == "CCX" and len(item["wires"]) == 3 and len(set(item["wires"])) == 3


def context(items):
    return all(item.get("condition") is None for item in items) and len({item.get("stage") for item in items}) == 1


def rewrite_once(gates):
    source = deepcopy(gates)
    for index, item in enumerate(source):
        item.setdefault("lineage", [item.get("id", index)])
    output, certificates = [], []
    index = 0
    while index < len(source):
        replacement = rule = identity = None
        count = 0
        if index + 2 < len(source):
            first, middle, last = source[index:index + 3]
            if ccx(first) and ccx(last) and context((first, middle, last)) and middle["kind"] == "Z" and middle["wires"] == first["wires"][-1:] and last["wires"][-1] == first["wires"][-1] and set(first["wires"][:2]) == set(last["wires"][:2]):
                a, b, target = first["wires"]
                replacement = [("Z", (target,)), ("CZ", (a, b))]
                rule, count = "phase_conjugation", 3
                identity = "CCX(a,b,t);Z(t);CCX(a,b,t) = Z(t);CZ(a,b)"
        if replacement is None and index + 1 < len(source):
            first, last = source[index:index + 2]
            if ccx(first) and ccx(last) and context((first, last)):
                controls, other = set(first["wires"][:2]), set(last["wires"][:2])
                target, second_target = first["wires"][-1], last["wires"][-1]
                if target == second_target and controls == other:
                    replacement = []
                    rule, count, identity = "inverse_pair", 2, "CCX^2 = I"
                elif controls == other and target != second_target:
                    a, b = first["wires"][:2]
                    replacement = [("CX", (target, second_target)), ("CCX", (a, b, target)), ("CX", (target, second_target))]
                    rule, count = "shared_product_fanout", 2
                    identity = "Two identical products on two arbitrary targets use one CCX and two CX"
                elif target == second_target and len(controls & other) == 1:
                    a = next(iter(controls & other))
                    b, c = next(iter(controls - {a})), next(iter(other - {a}))
                    replacement = [("CX", (b, c)), ("CCX", (a, c, target)), ("CX", (b, c))]
                    rule, count = "shared_control_factor", 2
                    identity = "ab XOR ac = a(b XOR c)"
        if replacement is None:
            output.append(source[index])
            index += 1
            continue
        consumed = source[index:index + count]
        certificate = {
            "rule": rule, "identity": identity,
            "source_gate_ids": sorted({identifier for item in consumed for identifier in item["lineage"]}),
            "source_origins": [item["origin"] for item in consumed],
            "preconditions": ["unconditional gates", "same stage", "valid distinct CCX wires", "adjacent matched window"],
            "clean_target_required": False,
            "toffolis_removed": sum(item["kind"] == "CCX" for item in consumed) - sum(kind == "CCX" for kind, _ in replacement),
        }
        certificates.append(certificate)
        for kind, wires in replacement:
            item = gate(kind, *wires, stage=consumed[0]["stage"])
            item["origin"] = consumed[0]["origin"]
            item["lineage"] = certificate["source_gate_ids"]
            item["rewrite_certificate"] = certificate
            output.append(item)
        index += count
    for index, item in enumerate(output):
        item["id"] = index
    return output, certificates


def karatsuba_two_bit():
    """Seven-qubit XOR polynomial product, including arbitrary outputs."""
    before = [gate("CCX", 0, 2, 4), gate("CCX", 0, 3, 5), gate("CCX", 1, 2, 5), gate("CCX", 1, 3, 6)]
    after = [gate("CX", 4, 5), gate("CX", 6, 5), gate("CCX", 0, 2, 4), gate("CCX", 1, 3, 6),
             gate("CX", 4, 5), gate("CX", 6, 5), gate("CX", 0, 1), gate("CX", 2, 3),
             gate("CCX", 1, 3, 5), gate("CX", 2, 3), gate("CX", 0, 1)]
    for item in before + after:
        item["origin"] = {"field_node": "polynomial_product", "expansion": "c ^= (a0 + a1*z)*(b0 + b1*z) over GF(2)[z]"}
    return before, after
