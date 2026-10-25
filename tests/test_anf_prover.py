import itertools
import random
import unittest

from architecture.anf_prover import evaluate, prove_equal, run
from architecture.rewrites import gate, karatsuba_two_bit, rewrite_once


def as_tuples(gates):
    return [(item["kind"], *item["wires"]) for item in gates]


def brute(gates, n):
    out = []
    for bits in range(1 << n):
        state, phase = dict(enumerate((bits >> w & 1) for w in range(n))), 0
        for kind, *ws in gates:
            if kind == "X": state[ws[0]] ^= 1
            elif kind == "CX": state[ws[1]] ^= state[ws[0]]
            elif kind == "CCX": state[ws[2]] ^= state[ws[0]] & state[ws[1]]
            elif kind == "SWAP": state[ws[0]], state[ws[1]] = state[ws[1]], state[ws[0]]
            elif kind == "Z": phase ^= state[ws[0]]
            elif kind == "CZ": phase ^= state[ws[0]] & state[ws[1]]
            elif kind == "CCZ": phase ^= state[ws[0]] & state[ws[1]] & state[ws[2]]
        out.append((tuple(state[w] for w in range(n)), phase))
    return out


class ProverTest(unittest.TestCase):
    def test_every_rewrite_rule_is_proved(self):
        fixtures = [
            [gate("CCX", 0, 1, 2), gate("CCX", 1, 0, 2)],
            [gate("CCX", 0, 1, 3), gate("CCX", 0, 2, 3)],
            [gate("CCX", 0, 1, 2), gate("CCX", 0, 1, 3)],
            [gate("CCX", 0, 1, 2), gate("Z", 2), gate("CCX", 0, 1, 2)],
        ]
        for before in fixtures:
            after, certificates = rewrite_once(before)
            self.assertEqual(len(certificates), 1)
            self.assertEqual(prove_equal(as_tuples(before), as_tuples(after))[0], "proved")

    def test_karatsuba_is_proved(self):
        before, after = karatsuba_two_bit()
        self.assertEqual(prove_equal(as_tuples(before), as_tuples(after))[0], "proved")

    def test_ccx_cz_ccx_collapses_to_one_ccz(self):
        before = [("CCX", 0, 1, 2), ("CZ", 2, 3), ("CCX", 0, 1, 2)]
        after = [("CZ", 2, 3), ("CCZ", 0, 1, 3)]
        self.assertEqual(prove_equal(before, after)[0], "proved")

    def test_refutation_gives_a_real_counterexample(self):
        before = [("CCX", 0, 1, 2)]
        verdict, witness = prove_equal(before, [])
        self.assertEqual(verdict, "refuted")
        self.assertEqual(witness, {0: 1, 1: 1})

    def test_prover_agrees_with_brute_force_on_random_circuits(self):
        rng = random.Random(850000)
        kinds = ["X", "CX", "CCX", "SWAP", "Z", "CZ", "CCZ"]
        arity = {"X": 1, "Z": 1, "CX": 2, "SWAP": 2, "CZ": 2, "CCX": 3, "CCZ": 3}
        for _ in range(300):
            n = 4
            def random_circuit():
                return [(k, *rng.sample(range(n), arity[k])) for k in rng.choices(kinds, k=rng.randint(0, 6))]
            a, b = random_circuit(), random_circuit()
            same = brute(a, n) == brute(b, n)
            self.assertEqual(prove_equal(a, b, wires=set(range(n)))[0] == "proved", same)


if __name__ == "__main__":
    unittest.main()
