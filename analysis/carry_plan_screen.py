#!/usr/bin/env python3
"""Compare two proposed leaf extensions with upstream Rec2's cost grammar.

Source: d7f4e842c90df365b5c08a5e25b326aba53894f0,
src/point_add/skycof/adder.rs. This screens analytical costs, not circuits.
"""

import argparse
import json
import math
from pathlib import Path


def chunk_cost(n, available):
    left, held = n - 1, 0
    if not left:
        return 0.0
    if not available:
        return math.inf
    while left > available - held:
        room = max(0, available - held)
        if room < 2:
            return math.inf
        left -= min(room, left - room + 1)
        held += 1
    return n - 1 + 0.5 * (n - 1 - available)


def screen(width=257, scratch=128):
    old = [[math.inf] * (width + 1) for _ in range(scratch + 1)]
    tables = {name: [[math.inf] * (width + 1) for _ in range(scratch + 1)] for name in ("baseline", "vented_phase", "chunk_leaves")}
    for available in range(scratch + 1):
        for n in range(1, width + 1):
            if n - 1 <= available:
                old[available][n] = n - 1
            elif available:
                old[available][n] = min(old[available - 1][k] + 1 + old[available - 1][n - k] + 0.5 * old[available][k] for k in range(1, n))
            for name, table in tables.items():
                table[available][n] = min(n - 1 if n - 1 <= available else math.inf, 2 * (n - 1) - min(available, n - 1))
                if name == "chunk_leaves" and n - 1 > available:
                    table[available][n] = min(table[available][n], chunk_cost(n, available))
                if available and n - 1 > available:
                    for k in range(1, n):
                        phase = old[available][k]
                        if name == "vented_phase":
                            phase = min(phase, 2 * (k - 1) - min(available, k - 1))
                        cost = table[available - 1][k] + 1 + table[available - 1][n - k] + 0.5 * phase
                        table[available][n] = min(table[available][n], cost)
    savings = {name: max(tables["baseline"][a][n] - table[a][n] for a in range(scratch + 1) for n in range(1, width + 1)) for name, table in tables.items() if name != "baseline"}
    return {
        "source_commit": "d7f4e842c90df365b5c08a5e25b326aba53894f0",
        "scope": "analytical Rec2 cost-table extensions; no quantum lower bound or circuit validity claim",
        "maximum_word_width": width,
        "scratch_range": [0, scratch],
        "maximum_expected_toffoli_saving": savings,
        "conclusion": "No positive saving in the screened grammar; exclude these proposed changes",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(screen(), indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered)
    print(rendered, end="")
