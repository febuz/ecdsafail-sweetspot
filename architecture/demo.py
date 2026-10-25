"""Emit inspectable algebraic and phase-repair provenance for a small region."""

import argparse
import json
from pathlib import Path

from architecture.field_dag import affine_point_add
from architecture.provenance import Origin, RegionCompiler


def demonstration():
    graph = affine_point_add()
    compiler = RegionCompiler("division.partial_product", 5, 1, graph.nodes)
    # data bits 0,1 are dy[0:2]; bits 2,3 are inv_dx[0:2]. These
    # expressions are selected bilinear partial products, not complete
    # integer product bits: carry arithmetic is deliberately not inferred.
    # Bit 4 is a coherent accumulator that is not one of the defining controls.
    first = compiler.prepare_bilinear([[1, 1], [1, 1]], (0, 1), (2, 3), Origin("slope", "(dy[0] XOR dy[1]) * (inv_dx[0] XOR inv_dx[1])"))
    compiler.xor_into(first, 4, compiler.stage)
    compiler.recycle(first, compiler.stage)
    second = compiler.prepare_bilinear([[0, 1], [0, 0]], (0, 1), (2, 3), Origin("slope", "dy[0]*inv_dx[1]"))
    compiler.xor_into(second, 4, compiler.stage)
    compiler.recycle(second, compiler.stage)
    return {"field_program": graph.export(), "scratch_region": compiler.report(), "target_achievement": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(demonstration(), indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
