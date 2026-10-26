# Cheaper inversion: a scan across fields (2026-10-26)

**Question.** Is there a structurally cheaper inversion step, drawn from mathematics, physics or chemistry, for the walks that carry 95% of the leader's Toffolis?

**Leader per phase (expected T, `build.log`):**

| Phase | Expected T |
|---|---|
| Divide walk | 350.4k |
| Square | 34.1k |
| Multiply walk | 356.8k |

**Gate set** (`src/circuit.rs`): X, Z, CX, CZ, Swap, CCX/CCZ, reset, H-measure-reset, and classical conditions. There are no rotations.

## New measurement: the transcript sits at its local information floor

Model modes `lf_tail --info` and `--branch` in [`research/lf_tail`](../research/lf_tail).

- **Global accounting.** Rails plus transcript always encode exactly d, about 256 bits. The leader stores 2 forced signs, the choice, 2 shift letters and 2/3 of a record bit, about 5.67 bits per tick and ≈690 bits over the walk. On paper that is ~430 bits of redundancy, roughly a third of the peak width.
- **Local accounting.** For each tick I count the pre-states (pre-target and letter) that the leader's tick maps onto the same post-state. Mean Σ log₂(#preimages) is **694 bits** (fixed-length bound 725). Pruned to the fitted width table it is still 653–689 bits. So per tick the transcript genuinely needs ~5.6 bits, which is what the leader stores.
- **Where the redundancy sits.** It is entirely non-local: rail R1 starts as the classical constant p, a pin 122 ticks away. Using it means recomputing the walk (Bennett pebbling), and that trade was measured flat earlier (≈7,100 T per qubit against ≈600 for break-even).
- **Static entropy coding of the letters does not help either.** Per-tick marginal entropy totals 505 bits. The spread of rails plus coded tape across walks is the same as that of the rails alone: +46 bits at the 10⁻⁴ quantile on tick 100.

## Candidates by field

| Field | Idea | Verdict | Reason |
|---|---|---|---|
| Physics | Fourier-basis (Draper) arithmetic | out | needs rotations; the gate set has none |
| Physics | Measurement-based uncomputation | already used | 68% of CCX are HMR-cleaned; executed-T averaging is exploited |
| Physics | Phase estimation on U_d | out | yields discrete logs, not inverses; U_{d⁻¹} needs d^(p−2) |
| Physics / thermodynamics | Bennett pebbling (Landauer: erase by recomputation) | flat | ≈7,100 T per qubit against ≈600 break-even |
| Chemistry | Catalysis: borrowed/dirty ancillas, catalytic space | flat to negative | dirty-ancilla adders cost 2–4× T for a few qubits |
| Information theory | Transcript compression (base-5, Jump-2 style) | at the floor | measured above: local need ≈ stored |
| Mathematics | Fermat a^(p−2) | out | ≈270 modular multiplications ≈ 17M T; wins only in binary fields, where squaring is linear |
| Mathematics | Lehmer / half-gcd (matrix steps) | worse | a k-step matrix costs ≈4·256 T per bit of progress against the walk's ≈1.3·256 |
| Mathematics | Karatsuba / Toom for the payload | out at n = 256 | schoolbook still has the lowest Toffoli count at this size (Litinski 2024) |
| Mathematics | Integer cofactors with register sharing (Proos–Zalka) instead of the mod-p payload | not better | payload adds roughly halve, but two modular multiplications (y·u, erase via d) and the end-of-walk width (cofactors + y) eat the gain |
| Mathematics | Batch inversion, one walk | closed | [one-walk.md](one-walk.md): in place still needs 1/d′ |
| Mathematics | 2-adic (Hensel/Newton) inverse | out | cheap mod 2^k, but turning it into a mod-p inverse needs p⁻¹ mod d, which is GCD-equivalent |
| Mathematics | secp256k1 structure (pseudo-Mersenne p, GLV) | used / n.a. | the fold already uses p's form; GLV helps scalar multiplication, not a single add |
| Mathematics | Projective / Legendre-hash (inversion-free) | n.a. | the challenge requires the affine result in place |
| Statistics | Approximate windows (spend λ) | already used | the leader spends λ ≈ 16 and grinds |

## Conclusion

Every per-walk constant measured sits at the floor of its local model:
- payload ≈ 4.4 T per bit per tick against a ≈4n floor for 3 adds plus a fold;
- the transcript's local information equals what is stored;
- the walk count is the known minimum of two.

What remains is non-local: the transcript's pin to p, and the T-for-Q trade, which is flat.

A structural jump would need an inversion primitive outside these classes: a GCD with genuinely fewer than ~1.3 n-bit adds per bit of progress while staying comparison-free, or a payload that is not a full-width mod-p register. None was found in the literature (Roetteler 2017, Häner 2020, Long et al. 2026: 1.356M T × 1,419 Q ≈ 1.92B, worse than the leader).

## Tested: inversion without division, using squarings only (Fermat), 2026-10-26

[`research/squaring_only/fermat_pebble.py`](../research/squaring_only/fermat_pebble.py) computes a⁻¹ = a^(p−2) with ~253 squarings and 13 multiplications, made reversible by optimal pebbling (Knill recursion). Costs are calibrated on the leader: modular square-and-subtract 34.1k T, multiply ≈ 2× that.

**Why pebbling is unavoidable.** Squaring mod p is 2-to-1, so every intermediate power must be kept or recomputed. k pebbles reach a line of at most 2^k − 1 steps without exponential blow-up, so at least 9 extra 256-qubit registers are needed. That is already above the 1,234 cap before anything else.

| Pebbles k | T per point add | Peak Q | Score | vs leader |
|---|---|---|---|---|
| 6 | 916M | 2,364 | 2,165B | 2,366× |
| 9 | 392M | 3,132 | 1,228B | 1,341× |
| 11 (best) | 264M | 3,644 | 961B | 1,050× |
| all 266 kept | 38.5M | 68,924 | 2,651B | 2,896× |

**Verdict.** Squaring is indeed the cheapest single operation: 34k T against 350k for a division walk. But a division replaces ~266 sequential squarings, and the pebbling those need costs another factor of ~7. Division-free inversion is ~1,000× worse in score. Quarter-squares multiplication (ab = ((a+b)² − (a−b)²)/4) has no target here either: outside the walks the point add has only one product, and that is already a square.
