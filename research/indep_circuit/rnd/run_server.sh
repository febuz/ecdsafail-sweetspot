#!/usr/bin/env bash
# Full R16-R18 sweeps for a large machine. Usage: ./run_server.sh [N] [SEEDS...]
# Default N = 1,000,000 inputs per experiment and seeds 1 2. Uses all cores (multiprocessing). Writes only small
# JSON summaries to results/. Expected run time scales linearly in N; on a laptop N = 2,000 takes ~1 minute.
set -euo pipefail
cd "$(dirname "$0")"
N="${1:-1000000}"; shift || true
SEEDS="${*:-1 2}"
python3 test_rnd.py
for s in $SEEDS; do
  python3 r17_swapfree/euclid_variants.py "$N" "$s"
  python3 r16_payload/payload_schemes.py "$N" "$s"
  python3 r18_coding/codes.py "$N" "$s"
done
echo "done: results in $(pwd)/results"
