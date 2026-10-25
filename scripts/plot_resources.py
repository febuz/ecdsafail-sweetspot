#!/usr/bin/env python3
"""Render the saved official frontier and locally generated forward trace."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
snapshot = json.loads((ROOT / "data/public-frontier.json").read_text())
points = snapshot["pareto_frontier"]
fig, ax = plt.subplots(figsize=(8.5, 4.8), layout="constrained")
ax.plot([p["q"] for p in points], [p["t"] / 1e6 for p in points], color="#245b88", linewidth=1.8, marker=".", markersize=4, label="Officially measured Pareto frontier")
ax.axvline(1080, color="#aa6332", linestyle="--", linewidth=1)
ax.axhline(0.85, color="#aa6332", linestyle="--", linewidth=1)
ax.scatter([1080], [0.85], marker="*", s=150, facecolors="none", edgecolors="#aa6332", linewidths=1.5, label="Research target — unachieved")
for point, label, offset in ((snapshot["lowest_t_under_cap"], "1,080 Q / 1.838M T", (-125, 15)), (snapshot["global_leader"], "1,234 Q / 0.742M T", (-160, 25)), (snapshot["lowest_product_under_cap"], "885 Q / 2.163M T", (12, 15))):
    ax.annotate(label, (point["q"], point["t"] / 1e6), xytext=offset, textcoords="offset points", fontsize=9, arrowprops=dict(arrowstyle="-", color="#73808b"))
ax.set(xlim=(760, 1290), ylim=(0.6, 5.0), xlabel="Peak logical qubits", ylabel="Average executed Toffolis (millions)", title="ECDSA.fail resource frontier — public snapshot, 25 October 2026")
ax.grid(alpha=0.18)
ax.legend(loc="upper right", frameon=False, fontsize=9)
fig.savefig(ROOT / "docs/frontier.svg")
fig.savefig(ROOT / "docs/frontier.png", dpi=160)
plt.close(fig)

trace = json.loads((ROOT / "data/leader-peak-trace.json").read_text())
rooms = [row for row in trace["rooms"] if row["direction"] == "fwd"]
peaks = [row for row in trace["peaks"] if row["direction"] == "fwd"]
fig, ax = plt.subplots(figsize=(8.5, 4.4), layout="constrained")
ax.plot([row["tick"] for row in rooms], [row["active"] for row in rooms], label="Active before carry scratch", color="#245b88", linewidth=2)
ax.plot([row["tick"] for row in peaks], [row["peak"] for row in peaks], label="Peak during tick", color="#588b6b", linewidth=1.6)
ax.axhline(1080, label="Hard cap 1,080", color="#aa6332", linestyle="--")
ax.axhline(1050, label="Stretch 1,050", color="#8c667d", linestyle=":")
ax.set(xlabel="Forward-walk tick", ylabel="Logical qubits", title="Leader's generated forward-walk trace — local build, no new evaluator result", ylim=(1030, 1250))
ax.grid(alpha=0.18)
ax.legend(loc="upper left", frameon=False, fontsize=9)
fig.savefig(ROOT / "docs/peak-trace.svg")
fig.savefig(ROOT / "docs/peak-trace.png", dpi=160)
