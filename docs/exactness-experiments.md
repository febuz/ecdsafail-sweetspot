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

## The failure model: every observed failure is a walk failure (validated)

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
| widened table (below), 9,024 evaluator inputs | 13 | 11 | 11 | 0 | 2 |

**Consequences:**
- **The multiply leg is classified** without marker alignment. Its failures are the same walk failure, run on d′ = x₂ − x₃.
- **The two sources split in half.** On 10⁸ sampled walks the failure rate is **8.0·10⁻⁴ per leg**: 4.2·10⁻⁴ from width overflow and 3.8·10⁻⁴ from walks not parked within 122 ticks. 52 of 10⁸ walks are still unparked at tick 130, and 1 at tick 135.
- **The leader's λ follows directly:** λ_walk ≈ 2 · 9,024 · 8.0·10⁻⁴ ≈ **14.5**. A given stream passes all 9,024 shots with probability e^−14.5 ≈ 5·10⁻⁷, so the baked `TAIL_NONCE` reflects on the order of 10⁶ tries.
- **The two "real only" failures** in the widened build are clean in the walk model under every convention. They come from a second source that the widening itself switches on: the payload cells lose the wires the wider rails take and fall back to more approximate chunk-boundary compares. On the unmodified builds this source was 0 of 13,120 shots.

## Why the convex-hull proof is withdrawn

If the parity-driven signs are treated as adversarial, the point T = B = M is a fixed point:
- the forced steps give (T + B)/2 = B;
- deep is 0 and so inadmissible, which forces flat;
- e = 0.

A hull propagated through the branch maps therefore never contracts the max-norm. divsteps escapes the diagonal through δ; this walk escapes only 2-adically, because T ≡ B mod 2ᵏ together with |T − B| < 2ᵏ forces T = B. A worst-case bound for all d would need that integrality argument and is research-grade. The "≈1% for exactness" estimate in the previous version rested on the hull and is **withdrawn**. The measured costs follow.

## What lowering λ actually costs (measured price, sampled tail)

**Measured price.** Variant F with the table +1 bit on ticks 2..115 builds only with the walk cap raised to 1,236. Ticks 0, 1 and 116+ are pinned by RT0 and N2 asserts. Result: **+2,660 T** (743,140 → 745,800, ≈ **23 T per bit-tick**) and **+2 Q**. An extra tick costs ≈ 4.6k T over both legs (from the per-tick Toffoli counts between variant F's tick markers; estimate).

**Cheapest plans** ([`widen.py`](../research/lf_tail/widen.py), greedy over 80,107 failing walks out of 10⁸):

| Target per leg | λ on 9,024 shots | Ticks | Extra bit-ticks | ≈ T | Max extra bits on a tick |
|---|---|---|---|---|---|
| (leader) 8.0·10⁻⁴ | 14.5 | 122 | 0 | 0 | 0 |
| 1·10⁻⁴ | 1.8 | 124 | 366 | +17.6k (+2.4%) | 3–5 |
| 1·10⁻⁵ | 0.18 | 127 | 874 | +43k (+5.8%) | ~7–9 |
| 1·10⁻⁶ | 0.018 | 129 | 1,609 | +69k (+9.3%) | ~13 |
| 1·10⁻⁷ | 0.002 | 132 | 1,669 | +84k (+11.4%) | ~13 |

The T column leaves out qubits. Rails widened by k bits on ticks where the walk sits at the cap cost up to 2k Q, unless the payload gives the room back, and that is exactly what switches on the payload's approximate compares. So the cost in score is higher still.

**Verdict.** A leapfrog circuit that passes without grinding (λ ≲ 0.2) costs at least about 6% T plus several qubits: roughly 975M+ against the leader's 915.3M. The leader's lead rests to a large extent on grinding a λ ≈ 14.5 circuit, not on the walk being cheap and exact. The structural reason for the tail is that a slow walk is a few ticks behind, and at about 2 bits per tick that lag becomes 6–10 bits of width on the late ticks.

## hddivsteps: checked, not prototyped

- **Bound reproduced from data:** sipa's precomputed hull tables (`half_delta_output.txt`) give **591** iterations for all 0 ≤ g ≤ f ≤ p (plain divsteps: 725). External code was not executed; only the published table was read.
- **Toffoli estimate:** 591 halving steps against ≈607 average halvings for the leapfrog walk (113 ticks × ≈5.4). Per step, the leader's per-halving payload cost (≈577 T) plus a mandatory 256-wire conditional swap gives ≈591 × 833 ≈ **490k T per inversion, ≈1.4×**.
- **Width: decisive.** Two history bits per step means ≈**1,182 extra qubits** unless they are decoded. Decoding is the andigu route (≈4.0M T at 935 Q). hddivsteps is therefore not a near-term path under the 1,234/1,080 width caps.
