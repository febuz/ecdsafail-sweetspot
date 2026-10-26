# Exactness experiments: leapfrog (active) and hddivsteps

## Which walk the leader actually runs

`src/point_add/mod.rs:507` sets `LEAPFROG_SUBMISSION = true`, and `build()` routes through `leapfrog::enabled()` first (`mod.rs:236`). The HEO/skywalk recipe is installed but not used for the walks. *(Superseded: see the lever-A correction below.)* The active choice rule is `LF_W1`: deep/flat is decided by comparing the rails on a **21-bit top window** ([|T| > 2|B|]), with a 138-tick width table (`leapfrog.rs` recipe). The tape-decoding study ([tape-decoding.md](tape-decoding.md)) used the header's v₂ rule for the fourth step. The forced-step result holds for both rules; the fourth-step numbers apply to the header rule only.

## Leapfrog: where the divide leg fails (variant F, real circuit values)

Method: a rebuild with every post-pass disabled and an `eprintln` trace of the rail and payload wire IDs at each forward and reverse tick (stream unchanged; same 8 of 4,096 fresh inputs fail as in the leader). [`research/trace_rails.py`](../research/trace_rails.py) reads the actual integers on those wires from the classical simulation.

1. **Payload invariant.** On divide ticks 37–115 the target rail's payload satisfies **P = ±λ·R (mod p)** on every passing shot (0 violations over 158 ticks × 64 shots). Rails are odd; with `LF_LOWREL` the bit-0 wire is implicit. Of the 8 failing shots, 4 break this invariant inside the divide walk (first bad ticks 37, 104, 105, 110). The other 4 keep it through the whole divide, so they fail later, in the multiply leg.
2. **Mechanism: rail-width margin.** For each tick and shot, margin = available rail width − signed bits needed. Over ticks 4–115:

| Group | Zero-margin events |
|---|---|
| 4,088 passing shots | **2** isolated events (ticks 35, 37) |
| 4 divide-failing shots | **runs of 4–12 consecutive ticks** (e.g. shot 900: ticks 103–115) |
| 4 multiply-failing shots | none in the divide |

**Verdict for the divide leg: class (b), envelope width.** The empirically fitted rail-width table (2M-sample refit, β = 1.020) is one bit too narrow on rare slow walks. The intermediate T ± B then overflows the rail. This contradicts the earlier claim, which rested on a model with the wrong fourth-step rule, that the failures "are not from the envelope". That claim is withdrawn.

3. **Multiply leg: resolved below** (walk on d′ = x₂ − x₃; see the failure model). Original note: Its builder op indices do not align with the stream: `SQTOP` inserts 480 ops in the square and `pp_simplify` removes 22. Passing shots show spurious zero margins at every tested offset. A marker-op alignment is needed before this leg can be classified.

## Correction: the active walk is lever A (`a2_rails.rs`), not plain leapfrog W1

`A2_DEFAULT = true` (`a2_rails.rs:8`) replaces the walk on ticks 1..120. It has **122 ticks**, a barrel cap e ≤ 7 with at most one e ≥ 4 event per same-rail triple, and its own window schedule (L = 22/13/17/22/19/17/15/13/11). It also has its own width table, `a2_R122_steps.txt` (W n0 n1 n2 nb, peel refit over 2M samples). The leader source carries an integer reference model of this walk, `a2_ref::walk_t0`, which its own test checks against the circuit's tape letters.

Two more corrections:
- `mod.rs:494` `clear_process_env()` wipes the whole process environment at start-up. Any variant set through environment variables is therefore a no-op. That explains why variants A and C were byte-identical to the leader.
- The later entries of `install_recipe` override earlier ones: `LF_MERGED_WIN` is 54, not 56.

## The failure model: the walk explains ~83% of failures (validated)

[`research/lf_tail`](../research/lf_tail) is a Rust port of `a2_ref::walk_t0`, about 150k walks/s. For each tick it records the signed width each value needs and compares it with the fitted table:
- W: the rails;
- n0, n1: the forced sums;
- n2: the taken choice sum;
- nb: the barrel input.

It also checks whether both rails are ±1 after tick 121 ("parked").

Each point add runs two walks: the divide on d = x₂ − x₁ and the multiply leg on d′ = x₂ − x₃. The model flags an input when either walk overflows or fails to park. The convention fitted to the data is that the forced sums may be one bit wider than the table (the adder keeps its carry) and every other column is strict. [`validate.py`](../research/lf_tail/validate.py) gives:

| Shot set | Real failures | Model flags | Both | Model only | Real only |
|---|---|---|---|---|---|
| variant F, seed 21, 4,096 fresh inputs | 8 | 8 (4 divide, 4 multiply) | 8 | 0 | 0 |
| leader stream, the evaluator's 9,024 Fiat-Shamir inputs | 0 | 0 | 0 | 0 | 0 |
| variant F, seeds 101–104, 4 × 4,096 fresh inputs | 28 | 22 | 22 | 0 | 6 |
| widened table (below), 9,024 evaluator inputs | 13 | 11 | 11 | 0 | 2 |

The leader's evaluator row is not evidence about the rate, because that stream was nonce-ground to pass exactly that shot set. It only shows that the model has no false positives there.

**Over the 20,480 fresh shots (seeds 21, 101–104):** 36 real failures, 30 flagged by the walk model, 0 false positives.
- **Measured per-shot rate:** 1.76·10⁻³, so λ ≈ **15.9** on 9,024 shots.
- **Split:** the walk accounts for ≈ **13.2**; non-walk failures account for ≈ **2.6** (6 shots, Poisson error large).
- **Non-walk source:** consistent with the payload's documented λ knobs (`LF_MERGED_WIN` 54, `LF_CELL_FOLD_MIN`, approximate chunk compares, the T3P1 majority pack).

**Consequences:**
- **The multiply leg is classified** without marker alignment. Its walk failures are the same walk failure, run on d′ = x₂ − x₃.
- **The two failure types overlap.** In 10⁸ sampled walks the walk-failure rate is **8.0·10⁻⁴ per leg**. The `walk()` semantics give 122 ticks with the special last tick:

  | Failure type | Rate per leg |
  |---|---|
  | width overflow only | 3.1·10⁻⁴ |
  | not parked only | 1.7·10⁻⁴ |
  | both | 3.1·10⁻⁴ |

  On the extended walk (no special last tick), 38,283 walks park after tick 122, 45 after tick 130 and none after tick 132.
- **The leader's λ:** the sampled walk rate predicts λ_walk ≈ 2 · 9,024 · 8.0·10⁻⁴ ≈ 14.5. The measured total is ≈ 15.9. A given stream passes all 9,024 shots with probability e^−15.9 ≈ 10⁻⁷, so the baked `TAIL_NONCE` reflects on the order of 10⁷ tries.
- **The two "real only" failures** in the widened build are clean in the walk model under every convention. They come from a second source that the widening itself switches on: the payload cells lose the wires the wider rails take and fall back to more approximate chunk-boundary compares. On the unmodified builds this source was 0 of 13,120 shots.

## Why the convex-hull proof is withdrawn

If the parity-driven signs are treated as adversarial, the point T = B = M is a fixed point:
- the forced steps give (T + B)/2 = B;
- deep is 0 and so inadmissible, which forces flat;
- e = 0.

A hull propagated through the branch maps therefore never contracts the max-norm. divsteps escapes the diagonal through δ; this walk escapes only 2-adically, because T ≡ B mod 2ᵏ together with |T − B| < 2ᵏ forces T = B. A worst-case bound for all d would need that integrality argument and is research-grade. The "≈1% for exactness" estimate in the previous version rested on the hull and is **withdrawn**. The measured costs follow.

## What lowering λ actually costs (measured price, sampled tail)

**Measured price.** Variant F with the table +1 bit on ticks 2..115 builds only with the walk cap raised to 1,236. Ticks 0, 1 and 116+ are pinned by RT0 and N2 asserts. Result: **+2,660 T** (743,140 → 745,800, ≈ **23 T per bit-tick**) and **+2 Q**. An extra tick costs ≈ 4.6k T over both legs (from the per-tick Toffoli counts between variant F's tick markers; estimate).

**Cheapest plans** ([`widen.py`](../research/lf_tail/widen.py), greedy over 80,107 failing walks out of 10⁸). Limitations:
- **In-sample.** The plan is fitted and scored on the same walks, so the 10⁻⁶ and 10⁻⁷ rows (100 and 10 walks left) are optimistic.
- **Extra ticks.** Plans with more than 122 ticks reuse the extended walk and price the extra ticks at ≈4.6k T each, with no width table past tick 122.

| Target per leg | λ on 9,024 shots | Ticks | Extra bit-ticks | ≈ T | Max extra bits on a tick |
|---|---|---|---|---|---|
| (leader) 8.0·10⁻⁴ | 14.5 | 122 | 0 | 0 | 0 |
| 1·10⁻⁴ | 1.8 | 124 | 366 | +17.6k (+2.4%) | 3–5 |
| 1·10⁻⁵ | 0.18 | 127 | 874 | +43k (+5.8%) | ~7–9 |
| 1·10⁻⁶ | 0.018 | 129 | 1,609 | +69k (+9.3%) | ~13 |
| 1·10⁻⁷ | 0.002 | 132 | 1,669 | +84k (+11.4%) | ~13 |

The T column leaves out qubits. Rails widened by k bits on ticks where the walk sits at the cap cost up to 2k Q (measured +2 Q for k = 1; the 10⁻⁵ plan has 7–9 bits on some ticks, so roughly +2 to +18 Q), unless the payload gives the room back, and that is exactly what switches on the payload's approximate compares. So the cost in score is higher still.

**Verdict.** A leapfrog circuit that passes without grinding (λ ≲ 0.2) costs at least about 6% T plus several qubits for the walk alone. It must also buy out the payload's λ ≈ 2.6, which is not priced here: roughly 975M+ against the leader's 915.3M. The leader's lead rests to a large extent on grinding a λ ≈ 14.5 circuit, not on the walk being cheap and exact. The structural reason for the tail is that a slow walk is a few ticks behind, and at about 2 bits per tick that lag becomes 6–10 bits of width on the late ticks.

## Can a different walk rule thin the tail? (rule search, 2026-10-26)

The model now takes the decision rule as parameters (`LF_RULE`, `LF_EMAX`, `LF_M`/`LF_K`, `LF_LADD`/`LF_HUP`,
`LF_E8EVERY`), in both the park-only mode (`--park`, ~1M walks/s) and the full walk with widths. Sanity check: the
parameterised rule with the leader's settings reproduces the leader's counts exactly.

**Ticks needed per leg** (park only, 2·10⁷ walks, seed 13; the 10⁻⁶ column rests on ~20 walks, so ±1 tick):

| Variant | 10⁻⁴ | 10⁻⁵ | 10⁻⁶ |
|---|---|---|---|
| Leader: windows, e ≤ 7, ≤1 e≥4 per same-rail triple | 124 | 127 | 129 |
| A: compare window 4 bits higher (L+4, top+4) | 124 | 126 | 128 |
| Exact \|T\| > 2\|B\| compare (leader records) | 124 | 126 | 127 |
| B: A + ≤2 events per 7 same-rail ticks | 123 | 125 | 127 |
| e ≤ 15 (leader records) | 122 | 124 | 126 |
| B + e ≤ 11 | 122 | 123 | 125 |
| Exact compare + free records + e ≤ 15 | 121 | 123 | 124 |
| e ≤ 15 only on every 3rd / 6th / 12th tick | 123 / 123 / 124 | 125 / 126 / 127 | |

**Walk cost at 10⁻⁵ after refitting each variant's own width table** ([`refit.py`](../research/lf_tail/refit.py),
union bound over ticks, 2·10⁷ full walks, seed 31). The union bound overstates absolute cost: for the leader at
10⁻⁴ it gives +25.5k T, the exactly calibrated table ([`calibrate.py`](../research/lf_tail/calibrate.py)) +20.8k T,
the record-based greedy +17.6k T. So read the column as a ranking:

| Variant | Walk cost (ticks + width) | What the variant itself costs |
|---|---|---|
| Leader rule | +41.9k | 0 |
| A | +36.7k | ~4 more compare bits per tick ≈ 2 T × 4 × 122 × 4 traversals ≈ 3.9k |
| B | +31.2k | A, plus records 5 bits/7 ticks vs 2/3 (≈ +6 Q ≈ 3.6k T) and a non-positional code to decode |
| e ≤ 15 | +19.2k | a 4th payload rotation stage: `rot8` is 508 Fredkins on 256 wires for 3 stages, so ≈ 256 T × 122 ticks × 4 traversals ≈ 120k |
| B + e ≤ 11 | +17.1k | same payload stage, ≈ 120k |
| Exact compare | +8.7k | a full-width magnitude compare per tick, roughly 100k |

**Result.**
- **What drives the tail.** The tail comes from the barrel cap e ≤ 7. When the deep choice needs v > 8, the walk falls back to the flat ×½ step and loses about 7 bits. The record constraint (one e ≥ 4 per triple) comes second. Compare-window precision barely matters, because the window already sits at the anchor.
- **Cheap knobs net to ≈ 0.** The A and B knobs save 5–11k T of walk cost but cost about the same to implement.
- **Removing the real driver costs more than it saves.** The drivers that matter (e ≤ 15, exact compare) cost an order of magnitude more than they save, because every tick pays for them, both legs, forward and reverse. Restricting e ≥ 8 to a subset of ticks loses the gain about as fast as it saves the stage.
- **Conclusion.** No rule variant found here lowers the cost of exactness materially below the ≈ +43k T (5.8%) of the leader rule. The tail is intrinsic to an e ≤ 7 leapfrog.
- **Side finding.** For a typical walk the fitted width table sits 30–50 bits above what the walk needs. The table, like the tick count, is sized for the rare slow walks.

## hddivsteps: checked, not prototyped

- **Bound reproduced from data:** sipa's precomputed hull tables (`half_delta_output.txt`) give **591** iterations for all 0 ≤ g ≤ f ≤ p (plain divsteps: 725). External code was not executed; only the published table was read.
- **Toffoli estimate:** 591 halving steps against ≈607 average halvings for the leapfrog walk (113 ticks × ≈5.4). Per step, the leader's per-halving payload cost (≈577 T) plus a mandatory 256-wire conditional swap gives ≈591 × 833 ≈ **490k T per inversion, ≈1.4×**.
- **Width: decisive.** Two history bits per step means ≈**1,182 extra qubits** unless they are decoded. Decoding is the andigu route (≈4.0M T at 935 Q). hddivsteps is therefore not a near-term path under the 1,234/1,080 width caps.
