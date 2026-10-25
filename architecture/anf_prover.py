"""Symbolic equivalence proofs for {X, CX, CCX, Z, CZ, CCZ, SWAP, NEG} circuits.

Every such circuit acts as U|x> = (-1)^phi(x) |F(x)>. Two circuits are the
same unitary iff F and phi agree as Boolean functions, and a Boolean
function has a unique algebraic normal form (ANF) over GF(2). Tracking each
wire and the phase as an ANF in the input variables therefore *decides*
equivalence for all 2^n inputs at once: equal ANFs are a proof, unequal
ANFs come with a concrete counterexample input.

Polynomials are sets of monomials; a monomial is a bitmask of variables
(0 is the constant 1). Because wires are free variables, a proof for one
labelling holds for every instantiation with distinct wires.
"""


def mul(a, b):
    out = set()
    for x in a:
        for y in b:
            out ^= {x | y}
    return frozenset(out)


def xor(a, b):
    return frozenset(set(a) ^ set(b))


ONE = frozenset({0})


def run(gates, wires):
    """Symbolic state after `gates`; gates are (kind, wire, ...)."""
    index = {wire: i for i, wire in enumerate(sorted(wires))}
    state = {wire: frozenset({1 << index[wire]}) for wire in wires}
    phase = frozenset()
    for kind, *ws in gates:
        if kind == "X":
            state[ws[0]] = xor(state[ws[0]], ONE)
        elif kind == "CX":
            state[ws[1]] = xor(state[ws[1]], state[ws[0]])
        elif kind == "CCX":
            state[ws[2]] = xor(state[ws[2]], mul(state[ws[0]], state[ws[1]]))
        elif kind == "SWAP":
            state[ws[0]], state[ws[1]] = state[ws[1]], state[ws[0]]
        elif kind == "Z":
            phase = xor(phase, state[ws[0]])
        elif kind == "CZ":
            phase = xor(phase, mul(state[ws[0]], state[ws[1]]))
        elif kind == "CCZ":
            phase = xor(phase, mul(mul(state[ws[0]], state[ws[1]]), state[ws[2]]))
        elif kind == "NEG":
            phase = xor(phase, ONE)
        else:
            raise ValueError(f"no exact ANF semantics for {kind}")
    return state, phase


def evaluate(poly, assignment):
    return sum(all(assignment >> v & 1 for v in range(monomial.bit_length()) if monomial >> v & 1)
               for monomial in poly) & 1


def prove_equal(before, after, wires=None, up_to_global_phase=False):
    """Return ('proved', None) or ('refuted', counterexample)."""
    if wires is None:
        wires = {w for _, *ws in before + after for w in ws}
    left, left_phase = run(before, wires)
    right, right_phase = run(after, wires)
    difference = {wire: xor(left[wire], right[wire]) for wire in wires}
    phase_difference = xor(left_phase, right_phase)
    if up_to_global_phase:
        phase_difference = xor(phase_difference, ONE) if ONE <= phase_difference else phase_difference
    witnesses = [poly for poly in [*difference.values(), phase_difference] if poly]
    if not witnesses:
        return "proved", None
    # Any monomial of minimal degree in a non-zero ANF gives a witness input.
    poly = witnesses[0]
    monomial = min(poly, key=lambda m: m.bit_count())
    order = sorted(wires)
    return "refuted", {order[v]: 1 for v in range(len(order)) if monomial >> v & 1}
