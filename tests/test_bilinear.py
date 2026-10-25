import unittest

from architecture.bilinear import factor, wire_factors
from architecture.verify import run_checks


class BilinearTests(unittest.TestCase):
    def test_all_ones_matrix_shares_one_parity_product(self):
        self.assertEqual(len(factor([[1, 1], [1, 1]])), 1)

    def test_overlapping_operand_partitions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            wire_factors([[1]], (0,), (0,))

    def test_emitted_gates_and_measurements_on_coherent_inputs(self):
        report = run_checks()
        self.assertEqual(report["result"], "pass")
        self.assertEqual(report["measurement_branches"], 132)
        self.assertEqual(report["demo_factored_compute_toffolis"], 2)


if __name__ == "__main__":
    unittest.main()
