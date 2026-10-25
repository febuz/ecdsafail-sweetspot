#!/usr/bin/env python3
"""Read public ECDSA.fail measurements and rank a logical-qubit cap.

This reports evaluated submissions, including non-promoted resource points.
It does not treat an official 9,024-shot score as a universal proof.
"""

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BENCHMARK = "1ffb695a-309b-46b6-a728-2f97d8c7be74"
URL = f"https://api.ecdsa.fail/api/benchmarks/{BENCHMARK}/submissions"


def load_rows(source: str):
    if source.startswith(("https://", "http://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            payload = json.load(response)
    else:
        payload = json.loads(Path(source).read_text())
    return payload["submissions"]


def measured(row):
    metrics = row.get("officialMetrics") or {}
    q, t = metrics.get("qubits"), metrics.get("toffoli")
    if not isinstance(q, int) or not isinstance(t, int):
        return None
    if row.get("status") != "accepted" and row.get("rejectionReason") != "score did not improve current best":
        return None
    return {
        "id": row["id"],
        "q": q,
        "t": t,
        "score": row.get("officialScore") or q * t,
        "status": row.get("status"),
        "solver": row.get("solverUsername"),
        "created": row.get("createdAt"),
        "commit": row.get("submissionCommitSha") or row.get("promotedSourceRef"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=URL, help="Public API URL or saved JSON response")
    parser.add_argument("--max-qubits", type=int, default=1080)
    parser.add_argument("--target-toffoli", type=int, default=850000)
    parser.add_argument("--json-out", type=Path, help="Write a compact public measurement snapshot")
    args = parser.parse_args()

    points = [point for row in load_rows(args.source) if (point := measured(row))]
    allowed = [point for point in points if point["q"] <= args.max_qubits]
    if not allowed:
        raise SystemExit("No officially measured submissions under this qubit cap")

    leader = min(points, key=lambda p: (p["score"], p["q"], p["t"]))
    best_t = min(allowed, key=lambda p: (p["t"], p["q"]))
    best_score = min(allowed, key=lambda p: (p["score"], p["q"]))

    print(f"Scored submissions: {len(points)}; Q <= {args.max_qubits}: {len(allowed)}")
    for label, point in (("Global score", leader), ("Lowest T under cap", best_t), ("Lowest Q*T under cap", best_score)):
        print(f"{label}: Q={point['q']:,} T={point['t']:,} Q*T={point['score']:,} id={point['id']} status={point['status']}")

    target_score = args.max_qubits * args.target_toffoli
    strict_record_t = (leader["score"] - 1) // args.max_qubits
    print(f"Engineering target at cap: Q*T={target_score:,}")
    print(f"To beat current global product at Q={args.max_qubits:,}: T <= {strict_record_t:,}")

    # A point is nondominated if every narrower point has a strictly larger T.
    frontier = []
    lowest_t_so_far = float("inf")
    for point in sorted(points, key=lambda p: (p["q"], p["t"])):
        if point["t"] < lowest_t_so_far:
            frontier.append(point)
            lowest_t_so_far = point["t"]
    nearby = [point for point in frontier if args.max_qubits - 100 <= point["q"] <= args.max_qubits + 100]
    print("Pareto points near cap:")
    for point in nearby:
        print(f"  Q={point['q']:,} T={point['t']:,} Q*T={point['score']:,} id={point['id']}")

    if args.json_out:
        snapshot = {
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": URL,
            "benchmark_id": BENCHMARK,
            "scored_submission_count": len(points),
            "cap": args.max_qubits,
            "target_toffoli": args.target_toffoli,
            "global_leader": leader,
            "lowest_t_under_cap": best_t,
            "lowest_product_under_cap": best_score,
            "strict_record_toffoli_at_cap": strict_record_t,
            "pareto_frontier": frontier,
        }
        args.json_out.write_text(json.dumps(snapshot, indent=2) + "\n")


if __name__ == "__main__":
    main()
