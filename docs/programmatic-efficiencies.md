# Programmatic efficiencies: screened against the leader

This page checks each published technique and the rule set in [`architecture/`](../architecture) against the leader's **real gate stream**, not fixtures. The leader is commit `644857a` (official 1,234 Q / 741,719 average executed T). Every entry ends in one of three verdicts:

- **fires**: N Toffolis saved in the leader stream, with the accounting basis stated;
- **does not fire**: the pattern is absent, or the leader's own postpasses already remove it;
- **does not apply**: the technique targets a different cost (T-count, depth), a different algebra (GF(2) vs GF(p)) or a different circuit shape.

## 1. Local rewrite rules on the emitted stream

Method: [`analysis/stream_rule_screen.py`](../analysis/stream_rule_screen.py) decodes `ops.bin` (QECCOPSZ, 56-byte records) as a stream. For every CCX/CCZ it keeps the earlier Toffoli-class gates that commute exactly with every gate emitted after them, within a 256-op window. It then tests the rules in [`architecture/rewrites.py`](../architecture/rewrites.py) plus their CCZ analogues. `PUSH/POP_CONDITION`, `SWAP`, `R` and `HMR` act as barriers. The counts are **static** gates, so a hit under a classical condition saves less than one executed Toffoli.

Stream: the leader's final `ops.bin`, rebuilt locally with its unmodified `build_circuit` (all postpasses, 5 min). It contains 10,231,150 ops: 703,896 unconditioned CCX, 74,979 conditioned CCX and 179 CCZ.

| Measurement | Result |
|---|---:|
| Rule hits, window 256 ops ([`data/stream-rule-screen-w256.json`](../data/stream-rule-screen-w256.json)) | **0** |
| Rule hits, window 100,000 ops ([`data/stream-rule-screen-w100k.json`](../data/stream-rule-screen-w100k.json)) | **0** |
| Same control pair recurring within 64 Toffolis, commutation **ignored** (loose upper bound) | 13,871 |
| …same pair with *both controls unwritten in between* (identical product) | **79** (71 conditioned, 8 measured then recomputed 40k–500k ops later) |
| CCX targets cleaned by HMR measurement (Gidney measurement-based AND uncompute) | 526,875 of 778,875 (68%) |
| Leader's own `pp_simplify product/affine/quadratic/truth` passes | 22 / 0 / 0 / 0 ops removed |

**Verdict: does not fire.** The commutation-ignoring count shrinks from 13,871 to 79 once write versions are checked. Most repeated control pairs read *different values* of the same wires, so they are not common subexpressions. The 79 true repeats cap the possible saving at ≈0.01% of the Toffolis. The 8 measured-and-recomputed products would have to stay live across 40k–500k ops through the peak region, which trades the scarce resource (width) for a negligible Toffoli gain. Zero-Toffoli measured cleanup, the core of the TRSR "recycling" idea, is **already the leader's default** for 68% of its Toffolis. It is not a new lever.

## 2. Source-by-source transfer map

| Source (pinned commit) | Technique | Cost it optimizes | Verdict for this challenge |
|---|---|---|---|
| [eth-sri/Unqomp](https://github.com/eth-sri/Unqomp) `9d7e885` | Automatic ancilla uncomputation on a dependency graph of *qfree* gates; recompute instead of keep | Qubits, at extra gates | **Does not apply directly.** The leader already hand-schedules its uncomputation, and Unqomp neither models HMR/phase-repair nor optimizes Toffoli count. Its qfree/consume-edge test is the right *admissibility* check, and our `RegionCompiler.recycle` version check plays the same role. |
| [gmeuli/caterpillar](https://github.com/gmeuli/caterpillar) `4c6f766` | SAT-encoded reversible pebbling (Meuli et al. 2019) | Qubits vs. recompute Toffolis | **Applies to the walk history only.** The trace starts at 1,097 active qubits at tick 1, above the 1,080 cap. Pebbling the ~100-qubit history growth cannot close the width gap on its own. It needs the live-set breakdown at the `Y16_PEAK` sites (ledger experiment 1) first. |
| [eclipse-qrisp/Qrisp](https://github.com/eclipse-qrisp/Qrisp) `b470ed7` | Permeability DAG + depth-aware Kahn linearization | Depth | **Does not apply.** The score counts Toffolis, not depth. Its permeability notion (a gate is *permeable* on a wire when it is diagonal there) is exactly the commutation test the stream screen uses. |
| [google-deepmind/alphatensor_quantum](https://github.com/google-deepmind/alphatensor_quantum) `3def81a` | Symmetric-tensor (Waring) decomposition of the phase-polynomial signature tensor; Toffoli and CS gadgets | **T-count** | **Limited transfer.** A Toffoli gadget costs 2 T in its accounting. The challenge counts a CCX as one unit whatever its T cost, so T savings do not register. The cubic-term rank idea transfers only where outputs are pure phases (CCZ blocks), and the stream screen measures those. |
| [quantumlib/Qualtran](https://github.com/quantumlib/Qualtran) `638777f` `ecc/ec_add.py` | Litinski 2023 (arXiv:2306.08585) 6-step affine add with Kaliski inversion | Toffolis at ~2n+O(1) width | **Reference design, not directly comparable.** Litinski adds a *classical* point (lookup-loaded constants) inside a windowed Shor loop; the challenge adds two quantum points. Its step decomposition remains a useful independent audit of which products must be live at once. |
| [sipa/safegcd-bounds](https://github.com/sipa/safegcd-bounds) `06abb7f` | Convex-hull worst-case iteration bounds for divsteps / hddivsteps | Iteration count (Toffolis *and* history width) | **See §3.** The leader does not use divsteps, but the hull method is the tool to prove or tighten its empirical tick envelope. |
| [andigu/uncompute](https://github.com/andigu/uncompute) `64b5a13` `tasks/modinv-point-add` | Benchmarked uncomputation tasks incl. modular-inverse point add | Ancilla cleanup | **Not screened (not fetched: GitHub API outage mid-session).** Worth a follow-up because it targets the same primitive. |
| GF(2) bilinear / quadratic rank lowering ([`bilinear.py`](../architecture/bilinear.py), [`quadratic.py`](../architecture/quadratic.py)), two-bit Karatsuba ([`rewrites.py`](../architecture/rewrites.py)) | XOR-accumulated partial products | Toffolis | **Applies only where outputs are true parities** (phase oracles, HMR phase repair, XOR-accumulated tags). secp256k1 field arithmetic is GF(p) with carries. Integer Karatsuba also needs extra scratch, which works against the binding constraint (width). |

## 3. Iteration-count check (safegcd bounds vs. leapfrog)

For the secp256k1 prime (log₂ p ≈ 256.0), the proven worst-case iteration bounds are:

| Variant | Bound | Source |
|---|---:|---|
| divsteps, Bernstein–Yang theorem ⌊49b/34⌋, b = log₂(f²+4g²) | 741 | gcd.cr.yp.to safegcd paper |
| divsteps, convex-hull bound (g ≤ f ≤ M) | 724 | sipa/safegcd-bounds |
| **hddivsteps** (δ starts at ½), convex-hull bound | **591** | sipa/safegcd-bounds |

The leader does **not** use divsteps. Its `leapfrog.rs` walk runs ~122–136 ticks, depending on the lever. Each tick does four add-halve steps plus a 0–3-bit barrel strip, so it uses at least ~490 halvings, already below the 591 hddivstep bound. The tick count and the shrinking rail widths (`leapfrog_data/a2_R122_steps.txt`) come from an **empirical** envelope ("rsim peel refit … nfit=2,000,000"), not a proof.

Consequences:

1. Switching to hddivsteps would *not* reduce the iteration count. **Excluded** as a direct Toffoli lever.
2. The hull method is linear and works per branch, so it could *prove* a worst-case tick count and rail-width envelope for the leapfrog step's four branches. The current envelope is validated only on random samples (the evaluator runs 9,024 shots). A proof would either certify the envelope or exhibit a failing input. **Whether the envelope could shrink further is unknown** until that runs. This is a correctness-and-tightness tool, not a measured saving.

## 4. What this changes in the plan

- **Stop adding peephole and CSE rules.** The leader's stream is locally optimal for every pattern in `architecture/rewrites.py`, both for products and for cleanup. The rulebook remains useful as a *verifier* for new code, not as a source of savings.
- **The remaining levers are algorithmic, and both act on width:**
  1. *Live-set breakdown at the `Y16_PEAK` sites* (ledger experiment 1). Tick 1 already holds 1,097 active qubits, above the 1,080 cap. History pebbling (caterpillar-style, Knill's optimal chain DP) can address only the ~100-qubit growth across the walk. The baseline needs a different payload/rail encoding.
  2. *Hull-proved leapfrog envelope* (§3). A proven worst-case rail-width schedule could either certify the current envelope or show where rails can narrow. Narrower rails save qubits and Toffolis together.
- Every future claim must come from a full rebuild plus the stream screen, reported in the evaluator's accounting.
