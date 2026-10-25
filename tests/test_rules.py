import unittest

from architecture.rulebook import run_checks
from architecture.rewrites import gate, rewrite_once


class CalculationRules(unittest.TestCase):
    def test_rulebook_exact_and_coherent_checks(self):
        report = run_checks()
        self.assertEqual(report["result"], "pass")
        rules = report["rules"]
        self.assertEqual(rules["shared_product_fanout"]["after"]["toffolis"], 1)
        self.assertEqual(rules["phase_conjugation"]["after"]["toffolis"], 0)
        self.assertEqual(rules["two_bit_polynomial_karatsuba"]["after"]["toffolis"], 3)
        self.assertEqual(rules["quadratic_parity_factorization"]["examples"]["majority_carry"]["optimized_compute_toffolis"], 1)
        self.assertEqual(rules["quadratic_parity_factorization"]["exact_anf_reconstructions"], 2048)

    def test_conditions_and_stage_boundaries_block_rewrites(self):
        first = gate("CCX", 0, 1, 3)
        second = gate("CCX", 0, 2, 3)
        second["condition"] = "m0"
        self.assertEqual(rewrite_once([first, second])[1], [])
        second["condition"] = None
        second["stage"] = "different"
        self.assertEqual(rewrite_once([first, second])[1], [])

    def test_intervening_mutation_is_a_barrier(self):
        source = [gate("CCX", 0, 1, 3), gate("CX", 2, 0), gate("CCX", 0, 1, 3)]
        self.assertEqual(rewrite_once(source)[1], [])

    def test_provenance_survives_factoring(self):
        first = gate("CCX", 0, 1, 3, field_node="p0")
        second = gate("CCX", 0, 2, 3, field_node="p1")
        output, certificates = rewrite_once([first, second])
        self.assertEqual({item["field_node"] for item in certificates[0]["source_origins"]}, {"p0", "p1"})
        self.assertTrue(all(item["rewrite_certificate"] == certificates[0] for item in output))


if __name__ == "__main__":
    unittest.main()
