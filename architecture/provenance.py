"""A stage-local quadratic scratch compiler with explicit phase obligations."""

from dataclasses import asdict, dataclass

from circuits.sparse_recycle import Quadratic
from architecture.bilinear import monomials, wire_factors


def ordered_depth(gates, charged_kinds):
    """Dependency depth of the emitted wire order; no hardware timing model."""
    wires, outcomes = {}, {}
    maximum = 0
    for gate in gates:
        parents = [wires.get(wire, 0) for wire in gate["wires"]]
        if gate["condition"] is not None:
            parents.append(outcomes[gate["condition"]])
        depth = max(parents, default=0) + int(gate["kind"] in charged_kinds)
        for wire in gate["wires"]:
            wires[wire] = depth
        if gate["kind"] == "HMR":
            outcomes[gate["measurement_output"]] = depth
        maximum = max(maximum, depth)
    return maximum


@dataclass(frozen=True)
class Origin:
    field_node: str
    expansion: str


@dataclass
class Lease:
    wire: int
    stage: str
    generation: int
    function: Quadratic
    versions: dict[int, int]
    origin: Origin
    factors: tuple | None = None
    released: bool = False


class RegionCompiler:
    """Own a fixed scratch region; controls must remain valid until repair.

    `reserved_width` and `peak_active` are both reported. No claim is made
    that reserving disjoint stage pools decreases either resource globally.
    """
    def __init__(self, stage, data_qubits, scratch_qubits, field_nodes):
        self.stage = stage
        self.data_qubits = data_qubits
        self.scratch_qubits = scratch_qubits
        self.field_nodes = set(field_nodes)
        self.versions = {wire: 0 for wire in range(data_qubits)}
        self.generations = {wire: 0 for wire in range(data_qubits, data_qubits + scratch_qubits)}
        self.live: dict[int, Lease] = {}
        self.gates = []
        self.certificates = []
        self.peak_active = data_qubits
        self.next_measurement = 0
        self.naive_bilinear_terms = 0
        self.factored_bilinear_products = 0

    def emit(self, kind, wires, origin, purpose, condition=None, term=None):
        self.gates.append({
            "id": len(self.gates), "kind": kind, "wires": list(wires),
            "stage": self.stage, "origin": asdict(origin), "purpose": purpose,
            "condition": condition, "monomial_mask": term,
        })

    def new_lease(self, function, origin):
        if origin.field_node not in self.field_nodes or not origin.expansion:
            raise ValueError("Unknown field node or missing algebraic expansion")
        controls = {bit for term in function.terms for bit in range(term.bit_length()) if term >> bit & 1}
        if any(bit not in self.versions for bit in controls):
            raise ValueError("Scratch function reads an undeclared data control")
        free = [wire for wire in self.generations if wire not in self.live]
        if not free:
            raise ValueError("Fixed stage scratch budget exhausted")
        wire = free[0]
        lease = Lease(wire, self.stage, self.generations[wire], function, {bit: self.versions[bit] for bit in controls}, origin)
        self.live[wire] = lease
        self.peak_active = max(self.peak_active, self.data_qubits + len(self.live))
        return lease

    def prepare(self, function, origin):
        lease = self.new_lease(function, origin)
        for term in sorted(function.terms):
            bits = tuple(bit for bit in range(term.bit_length()) if term >> bit & 1)
            self.emit("X" if not bits else "CX" if len(bits) == 1 else "CCX", (*bits, lease.wire), origin, "compute", term=term)
        return lease

    def emit_factor(self, lease, left, right, condition=None):
        parity_gates = [("CX", (wire, left[0])) for wire in left[1:]] + [("CX", (wire, right[0])) for wire in right[1:]]
        purpose = "compute parity product" if condition is None else "phase repair in parity basis"
        for kind, wires in parity_gates:
            self.emit(kind, wires, lease.origin, purpose, condition=condition)
        self.emit("CCX" if condition is None else "CZ", (left[0], right[0], lease.wire) if condition is None else (left[0], right[0]), lease.origin, purpose, condition=condition)
        for kind, wires in reversed(parity_gates):
            self.emit(kind, wires, lease.origin, purpose, condition=condition)

    def prepare_bilinear(self, matrix, left, right, origin):
        left, right = tuple(left), tuple(right)
        factors = wire_factors(matrix, left, right)
        function = Quadratic(monomials(matrix, left, right))
        lease = self.new_lease(function, origin)
        lease.factors = factors
        self.naive_bilinear_terms += len(function.terms)
        self.factored_bilinear_products += len(factors)
        for first, second in factors:
            self.emit_factor(lease, first, second)
        return lease

    def xor_into(self, lease, target, stage):
        self.check_lease(lease, stage)
        if target not in self.versions or target in lease.versions:
            raise ValueError("A reader must not overwrite a control needed for phase repair")
        self.emit("CX", (lease.wire, target), lease.origin, "coherent partial-product reader")
        self.mutate_control(target)

    def check_lease(self, lease, stage):
        if stage != lease.stage or stage != self.stage:
            raise ValueError("Scratch lease cannot cross a stage boundary")
        if lease.released or self.live.get(lease.wire) is not lease or self.generations[lease.wire] != lease.generation:
            raise ValueError("Stale or released scratch lease")

    def mutate_control(self, wire):
        # This records an external dataflow change; it does not synthesize it.
        self.versions[wire] += 1

    def recycle(self, lease, stage):
        self.check_lease(lease, stage)
        if any(self.versions[bit] != version for bit, version in lease.versions.items()):
            raise ValueError("Phase repair cannot use controls whose values changed")
        measurement = f"m{self.next_measurement}"
        self.next_measurement += 1
        start = len(self.gates)
        self.emit("HMR", (lease.wire,), lease.origin, "X measurement and reset", condition=None)
        self.gates[-1]["measurement_output"] = measurement
        if lease.factors is not None:
            for first, second in lease.factors:
                self.emit_factor(lease, first, second, condition=measurement)
        else:
            for term in sorted(lease.function.terms):
                bits = tuple(bit for bit in range(term.bit_length()) if term >> bit & 1)
                self.emit("NEG" if not bits else "Z" if len(bits) == 1 else "CZ", bits, lease.origin, "phase repair", condition=measurement, term=term)
        certificate = {
            "wire": lease.wire, "stage": stage, "generation": lease.generation,
            "basis": "X (H followed by Z readout)", "outcome": measurement,
            "measured_function_anf": sorted(lease.function.terms),
            "bilinear_factor_wires": lease.factors,
            "phase_to_cancel": "(-1)^(m * f(data))", "control_versions": lease.versions,
            "repair_gate_ids": list(range(start + 1, len(self.gates))),
            "cleanup_toffolis": 0, "classical_outcome_bits": 1,
            "feedforward_latency": "hardware dependent; not estimated",
            "origin": asdict(lease.origin), "releasable": True,
        }
        self.certificates.append(certificate)
        lease.released = True
        del self.live[lease.wire]
        self.generations[lease.wire] += 1
        return certificate

    def report(self):
        toffolis = sum(gate["kind"] == "CCX" for gate in self.gates)
        return {
            "stage": self.stage, "reserved_width": self.data_qubits + self.scratch_qubits,
            "peak_active": self.peak_active, "unreleased_scratch": len(self.live),
            "logical_toffolis": toffolis,
            "ordered_toffoli_depth": ordered_depth(self.gates, {"CCX", "CCZ"}),
            "ordered_measurement_rounds": ordered_depth(self.gates, {"HMR"}),
            "depth_scope": "emitted wire and classical-dependency order; no routing, factory, or cycle timing",
            "bilinear_rank_lowering": {"direct_partial_product_toffolis": self.naive_bilinear_terms, "factored_product_toffolis": self.factored_bilinear_products},
            "measurement_count": self.next_measurement,
            "conditional_phase_gates": sum(gate["condition"] is not None and gate["kind"] in ("NEG", "Z", "CZ") for gate in self.gates),
            "classically_conditioned_gates": sum(gate["condition"] is not None for gate in self.gates),
            "hardware_accounting": {
                "scenario_4T_per_Toffoli": {"T_magic_states": 4 * toffolis, "assumption": "measurement-assisted decomposition with suitable ancilla and feedforward; costs omitted from Q"},
                "scenario_7T_per_Toffoli": {"T_magic_states": 7 * toffolis, "assumption": "exact unitary Clifford+T decomposition; not a physical-qubit estimate"},
                "physical_error_correction_qubits": None,
                "magic_state_factory_qubits": None,
                "wall_clock_time_and_energy": None,
            },
            "gates": self.gates, "cleanup_certificates": self.certificates,
            "scope": "partial-product scratch demonstration; no full field multiplication or ECDSA lowering",
        }
