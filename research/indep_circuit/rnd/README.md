# R16–R18 research harness

This folder prepares the three open items of the 1,050-qubit / ~830k-Toffoli paper design ([../THEORETICAL_1050Q_900k.md](../THEORETICAL_1050Q_900k.md), [../BACKLOG.md](../BACKLOG.md)) for large-scale runs. Everything is plain Python 3 (standard library only) and parallel over all cores. It writes only small JSON summaries to `results/`.

## Layout
| Path | Item | What it does |
|---|---|---|
| `common.py` | all | secp256k1 constants, seeded inputs, parallel `sweep` (mean, max, q99.99 per metric), `save` to results/ |
| `r17_swapfree/euclid_variants.py` | R17 | Euclid formulations with cofactor-checked inversion; counts iterations, zero-padding, swaps, realignment events, tape bits and the shared rails+tape peak |
| `r16_payload/payload_schemes.py` | R16 | payload schemes on the radix-4 walk, checked against y·d⁻¹; counts quartering, select-adds, corrections and folds, plus the largest register width in redundant schemes |
| `r18_coding/codes.py` | R18 | tape codes with real encode/decode round trips; shared peak per code |
| `test_rnd.py` | all | fast correctness tests (seconds) |
| `run_server.sh` | all | full sweeps: `./run_server.sh 1000000 1 2` (N inputs, seeds) |
| `results/` | all | JSON summaries; the laptop runs below are included as a baseline |

## How to run
```
python3 test_rnd.py                     # must print ok for all tests
./run_server.sh 2000 1                  # laptop smoke run (~1 minute)
./run_server.sh 1000000 1 2             # server: 1M inputs, two seeds
```
Each script can also run alone: `python3 r17_swapfree/euclid_variants.py N SEED`.

## Findings so far (laptop, 500–2,000 inputs, all inversions correct)
**R17, Euclid formulations:**

| Variant | Iterations (max / mean) | Zero padding | Swaps | Realign events | Shared peak (max) |
|---|---|---|---|---|---|
| C0: classic, bit-serial | 353 / 337 | 0 | 150 | 149 | 536 (Elias-gamma) |
| C1: radix-4 nearest, signed digits | **283 / 259** | 0 | 105 | 104 | 902 (fixed digit code) |
| C2: C1 with parity-fixed roles (no swaps) | 565 / 518 | **50%** | 0 | 104 | 1,555 |

- Removing swaps with a fixed role parity **doubles the iterations**: the naive form of R17 does not pay. Realignment events stay at one per step in every variant.
- The radix-4 iteration count is 283 at the maximum. The design document assumed 240 (`ceil(bitlen(q)/2)`); the first-digit position matters.

**R16, payload:**
- P1_exact is correct, with ~309 quarterings per inversion: the cost the R16 target P2 must remove.
- Lazy reduction with a Solinas fold every 16 iterations needs only **261 bits (+5)**, so deferred correction is cheap in qubits.

**R18, codes:**

| Code | Shared peak max | Shared peak mean | Round trip |
|---|---|---|---|
| Elias-gamma on quotients | **544** | 526 | ok |
| Gauss–Kuzmin Huffman with escape | 575 | | worse than Elias-gamma |
| Huffman on radix-4 (digit, step-end) symbols | 903 | | ok |
| Fixed log₂5 per digit | 900 | | |

- **Coding per digit is far from tight.** The tape must code whole quotients per step, even when the circuit processes two bits per iteration.

**Consequences for the paper design:**
- Use I ≈ 283 instead of 240 (about +18% on the per-iteration part).
- The tape codes quotients, not digits.
- Swap removal needs a non-parity idea.
- THEORETICAL_1050Q_900k.md has to be updated after the server runs.

## Open tasks for the server runs (each with its acceptance check)
1. **Tails.**
   - Task: run `./run_server.sh 1000000 1 2` and record the max and q99.99 of iterations, shared peak and register width.
   - Acceptance: numbers stable between seeds (max within ±2).
2. **R16: P2_scaled** (`r16_payload/payload_schemes.py`).
   - Task: implement a scheme without per-iteration quartering, for example a global per-iteration scale with one classical constant 4^−I at the end, or Horner on the update value with the step's carry absorbed into the next step.
   - Acceptance: 0 wrong results on 1M inputs; ops per iteration ≤ one select-add plus fold/4; maximum width reported.
3. **R17: new formulations** (`r17_swapfree/euclid_variants.py`). Candidates:
   - role bit folded into the digit sign (C3);
   - two-sided update with a role register (C4);
   - quotient-1 fast path where most steps are single subtractions (C5).
   - Acceptance: inversion ok on 1M inputs, iterations ≤ 300, swaps or padding priced ≤ 100 T per iteration.
4. **R18: quotient-level codes** (`r18_coding/codes.py`).
   - Tasks: an enumerative code for runs of quotient-1 steps, and adaptive Gauss–Kuzmin coding with Elias-gamma escape (the escape threshold being the parameter).
   - Acceptance: shared peak max ≤ 530 on 1M inputs; round trip ok; plus an estimate of the reversible encoder cost per step from its arithmetic (number of controlled constant adds and comparisons).
5. **Builder-level prototypes**, after 2–4: one iteration of the chosen payload scheme and one encode/decode block, written as Rust unit tests next to `../src/point_add/` (same style as `divide_and_multiply_256`). Each must report Toffoli and qubits from the simulator, with bad 0, garbage 0, phase 0.
