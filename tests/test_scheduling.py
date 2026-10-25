import itertools
import unittest

from architecture.rewrites import gate, karatsuba_two_bit
from architecture.rulebook import exact_basis_action, verify_identity
from architecture.scheduling import commute, expose_reuse, parallel_schedule


class SchedulingTests(unittest.TestCase):
    def test_all_reported_commutations_are_exact_on_four_qubits(self):
        gates = [gate("X", wire) for wire in range(4)] + [gate("Z", wire) for wire in range(4)]
        gates += [gate("CX", a, b) for a, b in itertools.permutations(range(4), 2)]
        gates += [gate("CZ", a, b) for a, b in itertools.combinations(range(4), 2)]
        gates += [gate("CCX", a, b, target) for a, b in itertools.combinations(range(4), 2) for target in range(4) if target not in (a, b)]
        for first in gates:
            for second in gates:
                if commute(first, second):
                    for bits in range(16):
                        self.assertEqual(exact_basis_action([first, second], bits), exact_basis_action([second, first], bits))

    def test_nonadjacent_product_can_be_reused(self):
        source = [gate("CCX", 0, 1, 3), gate("Z", 4), gate("CCX", 0, 2, 3)]
        result = expose_reuse(source)
        report = verify_identity(source, result["gates"], 5)
        self.assertEqual(report["after"]["toffolis"], 1)
        self.assertEqual(len(result["commutation_moves"][0]["crossed_source_gate_ids"]), 1)

    def test_mutating_control_prevents_reuse_exposure(self):
        source = [gate("CCX", 0, 1, 3), gate("CX", 2, 0), gate("CCX", 0, 1, 3)]
        self.assertEqual(expose_reuse(source)["rewrite_certificates"], [])

    def test_karatsuba_schedule_is_legal_and_uses_no_fanout(self):
        before, after = karatsuba_two_bit()
        first, second = parallel_schedule(before), parallel_schedule(after)
        verify_identity(before, first["gates"], 7)
        verify_identity(after, second["gates"], 7)
        self.assertEqual(first["toffoli_containing_layers"], 3)
        self.assertEqual(second["toffoli_containing_layers"], 2)
        for source, schedule in ((before, first), (after, second)):
            for layer in schedule["layers"]:
                wires = [wire for index in layer for wire in source[index]["wires"]]
                self.assertEqual(len(wires), len(set(wires)))

    def test_measurement_boundary_is_not_scheduled(self):
        with self.assertRaisesRegex(ValueError, "unconditional"):
            parallel_schedule([gate("HMR", 0)])


if __name__ == "__main__":
    unittest.main()
