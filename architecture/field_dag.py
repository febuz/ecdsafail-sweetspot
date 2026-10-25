"""Exact field expressions with origin tags and dependency-based pruning."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Node:
    name: str
    operation: str
    arguments: tuple[str, ...]
    origin: str
    classical: bool = False


class FieldDAG:
    def __init__(self, modulus):
        self.modulus = modulus
        self.nodes: dict[str, Node] = {}
        self.outputs: tuple[str, ...] = ()

    def add(self, name, operation, arguments=(), origin="", classical=False):
        if name in self.nodes or not origin:
            raise ValueError("Node names must be unique and algebraic origins explicit")
        if any(argument not in self.nodes for argument in arguments):
            raise ValueError("Every dependency must already exist")
        self.nodes[name] = Node(name, operation, tuple(arguments), origin, classical)
        return name

    def reachable(self):
        live = set()
        def visit(name):
            if name not in live:
                live.add(name)
                for argument in self.nodes[name].arguments:
                    visit(argument)
        for name in self.outputs:
            visit(name)
        return live

    def pruning_certificate(self):
        live = self.reachable()
        return {
            "rule": "remove unreachable field expressions before any reversible gates are emitted",
            "outputs": list(self.outputs),
            "retained": [name for name in self.nodes if name in live],
            "pruned": [name for name in self.nodes if name not in live],
            "gate_saving_claimed": False,
            "reason": "No gate backend or baseline gate subtree has been emitted",
        }

    def evaluate(self, inputs, prune=True):
        values = {}
        live = self.reachable() if prune else set(self.nodes)
        p = self.modulus
        for name, node in self.nodes.items():
            if name not in live:
                continue
            arguments = [values[argument] for argument in node.arguments]
            if node.operation == "input":
                value = inputs[name]
            elif node.operation == "add":
                value = arguments[0] + arguments[1]
            elif node.operation == "sub":
                value = arguments[0] - arguments[1]
            elif node.operation == "mul":
                value = arguments[0] * arguments[1]
            elif node.operation == "square":
                value = arguments[0] ** 2
            elif node.operation == "inverse":
                if arguments[0] % p == 0:
                    raise ValueError(f"Nonzero-domain obligation failed at {name}")
                value = pow(arguments[0], -1, p)
            else:
                raise ValueError(node.operation)
            values[name] = value % p
        return tuple(values[name] for name in self.outputs)

    def export(self):
        return {
            "modulus": str(self.modulus),
            "nodes": [asdict(node) for node in self.nodes.values()],
            "outputs": self.outputs,
            "domain_obligations": [{"node": name, "nonzero": node.arguments[0]} for name, node in self.nodes.items() if node.operation == "inverse"],
            "lowering_status": "symbolic field frontend only; no complete quantum circuit",
        }


def affine_point_add(modulus=2**256 - 2**32 - 977):
    """Generic affine addition; dx != 0 is an explicit domain obligation."""
    graph = FieldDAG(modulus)
    for name in ("px", "py", "qx", "qy"):
        graph.add(name, "input", origin=f"input.{name}", classical=name.startswith("q"))
    graph.add("dx", "sub", ("px", "qx"), "affine.dx = px - qx")
    graph.add("dy", "sub", ("py", "qy"), "affine.dy = py - qy")
    graph.add("inv_dx", "inverse", ("dx",), "affine.inv_dx = dx^-1; requires dx != 0")
    graph.add("slope", "mul", ("dy", "inv_dx"), "affine.slope = dy * inv_dx")
    graph.add("slope2", "square", ("slope",), "affine.slope2 = slope^2")
    graph.add("rx_partial", "sub", ("slope2", "px"), "affine.rx_partial = slope^2 - px")
    graph.add("rx", "sub", ("rx_partial", "qx"), "affine.rx = slope^2 - px - qx")
    graph.add("x_delta", "sub", ("px", "rx"), "affine.x_delta = px - rx")
    graph.add("y_product", "mul", ("slope", "x_delta"), "affine.y_product = slope * (px - rx)")
    graph.add("ry", "sub", ("y_product", "py"), "affine.ry = slope * (px - rx) - py")
    graph.outputs = ("rx", "ry")
    return graph
