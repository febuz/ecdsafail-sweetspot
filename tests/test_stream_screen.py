import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from analysis.stream_rule_screen import exact_repeats, screen

NONE = (1 << 64) - 1
RECORD = struct.Struct("<II6Q")


def op(kind, c2=NONE, c1=NONE, target=NONE):
    return RECORD.pack(kind, 0, c2, c1, target, NONE, NONE, NONE)


@unittest.skipUnless(shutil.which("zstd"), "needs the zstd CLI")
class StreamScreenTest(unittest.TestCase):
    def write(self, ops):
        body = subprocess.run(["zstd", "-c"], input=b"".join(ops), capture_output=True, check=True).stdout
        path = Path(tempfile.mkdtemp()) / "ops.bin"
        path.write_bytes(b"QECCOPSZ" + struct.pack("<Q", len(ops)) + body)
        return path

    def test_commuting_pairs_fire_and_blocked_pair_does_not(self):
        path = self.write([
            op(13, 0, 1, 2), op(8, NONE, 3, 4), op(13, 1, 0, 2),   # inverse pair past a commuting CX
            op(13, 0, 1, 5), op(8, NONE, 5, 6), op(13, 0, 1, 5),   # CX reads target 5: blocked
            op(14, 0, 1, 9), op(14, 9, 1, 0),                      # CCZ inverse pair
        ])
        hits = screen(path, 256, None)["rule_hits_toffolis_saved_static"]
        self.assertEqual(hits, {"ccz_inverse_pair/uncond": 2, "inverse_pair/uncond": 2})

    def test_repeat_requires_unwritten_controls(self):
        path = self.write([
            op(13, 0, 1, 2), op(12, NONE, NONE, 2), op(13, 0, 1, 3),  # measured, then recomputed
            op(6, NONE, NONE, 0), op(13, 0, 1, 4),                    # control 0 rewritten: new product
        ])
        report = exact_repeats(path)
        self.assertEqual(report["identical_product_repeats"]["measured_then_recomputed"], 1)
        self.assertEqual(report["ccx_targets_cleaned_by_hmr"], 1)


if __name__ == "__main__":
    unittest.main()
