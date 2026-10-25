#!/usr/bin/env python3
"""Extract the leader's existing live-qubit trace; does not modify a circuit."""

import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("log", type=Path)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
rooms, peaks, totals = [], [], []
for line in args.log.read_text(errors="replace").splitlines():
    if match := re.search(r"Y15_ROOM (\w+) t=(\d+) active=(\d+) room=(\d+)", line):
        direction, tick, active, room = match.groups()
        rooms.append(dict(direction=direction, tick=int(tick), active=int(active), room=int(room)))
    if match := re.search(r"Y16_PEAK (\w+) t=(\d+) peak=(\d+) cap=(\d+)", line):
        direction, tick, peak, cap = match.groups()
        peaks.append(dict(direction=direction, tick=int(tick), peak=int(peak), cap=int(cap)))
    if line.startswith("HEO_TOTAL "):
        totals.append(line)
if not rooms or not peaks:
    raise SystemExit("No expected Y15_ROOM/Y16_PEAK trace found; do not infer zero usage")
result = {
    "source_commit": "644857a7724560048a4ce23b3d8364a81010881c",
    "scope": "generated-circuit trace only; independent local evaluation not completed",
    "max_active_before_scratch": max(row["active"] for row in rooms),
    "max_reported_peak": max(row["peak"] for row in peaks),
    "total_reports": totals,
    "rooms": rooms,
    "peaks": peaks,
}
text = json.dumps(result, indent=2) + "\n"
if args.output:
    args.output.write_text(text)
else:
    print(text, end="")
