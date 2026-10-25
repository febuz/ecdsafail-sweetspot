import unittest

from architecture.demo import demonstration
from architecture.field_dag import affine_point_add
from architecture.provenance import Origin, RegionCompiler
from circuits.sparse_recycle import Quadratic


class FieldTests(unittest.TestCase):
    def test_all_generic_curve_pairs_over_small_field(self):
        p = 17
        graph = affine_point_add(p)
        points = [(x, y) for x in range(p) for y in range(p) if (y*y - x*x*x - 7) % p == 0]
        cases = 0
        for px, py in points:
            for qx, qy in points:
                if px == qx:
                    continue
                rx, ry = graph.evaluate(dict(px=px, py=py, qx=qx, qy=qy))
                self.assertEqual((ry*ry - rx*rx*rx - 7) % p, 0)
                slope = ((py - qy) * pow(px - qx, -1, p)) % p
                self.assertEqual((ry + py) % p, (slope * (px - rx)) % p)
                cases += 1
        self.assertGreater(cases, 100)

    def test_inverse_domain_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "Nonzero-domain"):
            affine_point_add(17).evaluate(dict(px=1, py=2, qx=1, qy=3))

    def test_pruning_uses_dependencies_not_magnitude(self):
        graph = affine_point_add(17)
        graph.add("unused_square", "square", ("dx",), "diagnostic.dx_squared")
        self.assertEqual(graph.pruning_certificate()["pruned"], ["unused_square"])
        graph.outputs += ("unused_square",)
        self.assertEqual(graph.pruning_certificate()["pruned"], [])


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.graph = affine_point_add()
        self.origin = Origin("slope", "dy[0] * inv_dx[0]")
        self.function = Quadratic(frozenset({3}))

    def test_phase_repair_precedes_reuse(self):
        compiler = RegionCompiler("division", 2, 1, self.graph.nodes)
        first = compiler.prepare(self.function, self.origin)
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            compiler.prepare(self.function, self.origin)
        compiler.recycle(first, "division")
        second = compiler.prepare(self.function, self.origin)
        self.assertEqual(first.wire, second.wire)
        self.assertEqual(second.generation, first.generation + 1)
        self.assertEqual([gate["kind"] for gate in compiler.gates[:3]], ["CCX", "HMR", "CZ"])

    def test_mutated_control_blocks_recycle(self):
        compiler = RegionCompiler("division", 2, 1, self.graph.nodes)
        lease = compiler.prepare(self.function, self.origin)
        compiler.mutate_control(0)
        with self.assertRaisesRegex(ValueError, "values changed"):
            compiler.recycle(lease, "division")
        self.assertFalse(lease.released)
        self.assertEqual(compiler.report()["measurement_count"], 0)

    def test_cross_stage_use_is_rejected(self):
        compiler = RegionCompiler("division", 2, 1, self.graph.nodes)
        lease = compiler.prepare(self.function, self.origin)
        with self.assertRaisesRegex(ValueError, "stage boundary"):
            compiler.recycle(lease, "square")

    def test_every_gate_has_origin_and_every_scratch_is_repaired(self):
        report = demonstration()["scratch_region"]
        self.assertTrue(all(gate["origin"]["field_node"] == "slope" for gate in report["gates"]))
        self.assertEqual(report["unreleased_scratch"], 0)
        self.assertEqual(report["logical_toffolis"], 2)
        self.assertEqual(report["measurement_count"], 2)
        self.assertEqual(report["peak_active"], 6)
        self.assertEqual(report["ordered_toffoli_depth"], 2)
        self.assertEqual(report["ordered_measurement_rounds"], 2)


if __name__ == "__main__":
    unittest.main()
