# Realistic assessment (2026-10-27): can this work beat the current submissions?

## Where we stand
| | Toffoli | Qubits | Score | Status |
|---|---|---|---|---|
| Leader 9ef3139 | 741,645 | 1,234 | 0.915B | approximate + nonce-ground |
| Theta (low-qubit) | 2.22M | 893 | 1.98B | submitted |
| Community route 39e28ee | 1.32M | 1,152 | 1.52B | submitted (older) |
| DivPay, official eval (phase 2b) | 3.32M | 2,139 | 7.10B | measured, 9024/9024 exact, no grinding |
| DivPay, current code | ~2.88M | 1,963 | ~5.65B | unit tests |
| DivPay after backlog I2–I5 | ~2.9M | ~1,660 | ~4.8B | estimate |
| Euclid shared register, design A | ~1.5M | ~1,100 | ~1.6B | paper, with the measured 283 radix-4 iterations |
| Euclid design E/F | ~0.84–0.95M | 1,050 | ~0.9–1.0B | paper; needs new results (R16, R17) |

## 1. Lowest score (beat the leader): not realistic
- What is built and measured is 6–8× the leader; after the backlog it is still ~5×.
- Only paper design E/F comes close, and it rests on swap-free Euclid step boundaries (R17). The first test of that idea failed: parity-fixed roles doubled the iterations (rnd/README.md).

## 2. A point on the curve at ~1,050–1,150 qubits: possible, not probable
- Near 1,100 Q the curve sits at about 1.5M T, interpolating between the 1,152-qubit route and Theta. Design A is on paper at ~1.5M, so roughly on the curve, not clearly below it.
- Paper estimates carry about ±30% uncertainty.
- Building it means weeks of work on the server: shared register, radix-4 iterations, quotient-level coding.
- The chance of clearly beating the existing point there is small to moderate.

## 3. What is unique in this work
- **Exact circuits without grinding.** Nearly all strong submissions use approximations (measured λ ≈ 16–23 failures per 9024 shots) plus a ground nonce. DivPay passes 9024/9024 without either. On an "exact only" curve the work stands stronger, but the leaderboard does not distinguish it.
- **Measured limits and research tooling:**
  - the validated failure model of the leader (`research/lf_tail`);
  - the local information floor of the transcript (`docs/inversion-crossfield.md`);
  - the Euclid shared register (550 bits, against 850–894 for divsteps);
  - the R16–R18 harness (`rnd/`).

  This is publishable knowledge independent of the leaderboard.

## Recommendation: treat the Euclid path as research with hard stop points
| Gate | Continue only if | Otherwise |
|---|---|---|
| M5 (R11 on the server) | division ≤ 1.2M T at ≤ 1,150 Q on paper, confirmed with 1M-input tails | stop the low-qubit path |
| M6 (R16–R18) | a priced builder-level prototype beats the curve at ~1,100 Q by ≥ 10% | publish the analysis and keep the exact circuit |

If the gates fail, the realistic result is an exact circuit (≈ 4.8B after the backlog) plus the published analysis, not a leaderboard win.
