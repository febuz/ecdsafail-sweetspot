# The leader passes only on its own shot set

## Experiment

The evaluator's 9,024 test points are a SHAKE256 (Fiat–Shamir) function of the op stream, and it allows zero mismatches. We appended a Clifford no-op pair `X(q); X(q)` to the leader's final `ops.bin` (commit `644857a`). That changes the hash but not the circuit, the Toffoli count or the qubit count. We then ran the leader's own `eval_circuit`:

| Stream | Classical mismatches (of 9,024) | Verdict |
|---|---:|---|
| Leader as built | 0 | OK, 741,719.312 × 1,234 |
| + `X(0); X(0)` | 19 | FAILED |
| + `X(1); X(1)` | 18 | FAILED |
| + `X(2); X(2)` | 19 | FAILED |

Independently, [`analysis/live_width.py`](../analysis/live_width.py) on fresh secp256k1 inputs gives 4,088/4,096 and 4,087/4,096 correct (seeds 21 and 22), i.e. a failure rate of ≈0.21%. That is **≈19 expected failures per 9,024 shots**.

## The source states the mechanism

- Its tuning packages cite a **"19.5 Lambda limit"** (`src/point_add/mod.rs`, around line 447), i.e. 19.5 expected failures per 9,024 shots, which matches the measured 18–19.
- `mod.rs:158–159`: `// Public-validation nonce (Leapfrog build: all 9024 Fiat-Shamir shots pass).` `"TAIL_NONCE" => "1171102834260"`, written into a 96-op identity tail (`mod.rs:200`).
- Several Toffoli cuts are labelled "lambda-priced" (e.g. `HEO_MB_SKIP2`, `HEO_DB_SKIP2` in `heo_carry.rs:115–118`): they buy Toffolis with expected failures.

At λ = 19.5, a single build passes with probability e^−19.5 ≈ 3×10⁻⁹. The published point is a deliberately approximate circuit plus a searched nonce whose shot set misses every failure.

## Where the failures are *not*

All 17 failing fresh inputs have ordinary geometry: no y₁ = ±y₂ case, and ≤122 walk ticks in the [`leapfrog_decode.py`](../research/leapfrog_decode.py) model. None exceeds the per-tick 99.9% rail-width quantile, against 0.9% of random walks. The failures are not from the walk-length envelope, and not from the stream-bound post-edits either: a rebuild without them fails on exactly the same inputs ([proofs](proofs.md)). Localization puts them 44% in the divide walk, 0% in the square and 56% in the multiply walk.

## Consequences for this repository

1. **No edit on top of the leader can pass as-is.** Any change, even a zero-cost one, reseeds the shots and fails about 19 of them. Every Toffoli saving measured against the leader must be re-priced against an exact (or λ ≪ 1) baseline.
2. **Approximation itself is legitimate; grinding is the issue.** The README says the Fiat–Shamir inputs exist so that "you cannot tune the circuit against the test set". A circuit with λ ≪ 1 (per-addition failure ≲ 10⁻⁵, the usual standard for approximate carries) passes without any search, and that remains a valid way to cut Toffolis without adding qubits. This repository does not grind nonces.
3. **Open measurement: the price of exactness.** The approximation knobs are hard-set inside the build recipe (`mod.rs:482` overwrites the environment), so pricing them takes source edits in a copy plus rebuilds. The target number is the leader's Toffoli count at λ ≤ 0.01 (failure ≤ 1.1×10⁻⁶ per shot). That defines an honest frontier point, and every pure-Toffoli lever should be measured against it.
