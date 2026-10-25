# Exactness experiments: leapfrog (active) and hddivsteps

## Which walk the leader actually runs

`src/point_add/mod.rs:507` sets `LEAPFROG_SUBMISSION = true`, and `build()` routes through `leapfrog::enabled()` first (`mod.rs:236`). The HEO/skywalk recipe is installed but not used for the walks. The active choice rule is `LF_W1`: deep/flat is decided by comparing the rails on a **21-bit top window** ([|T| > 2|B|]), with a 138-tick width table (`leapfrog.rs` recipe). The tape-decoding study ([tape-decoding.md](tape-decoding.md)) used the header's v₂ rule for the fourth step. The forced-step result holds for both rules; the fourth-step numbers apply to the header rule only.

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

3. **Multiply leg: unresolved.** Its builder op indices do not align with the stream: `SQTOP` inserts 480 ops in the square and `pp_simplify` removes 22. Passing shots show spurious zero margins at every tested offset. A marker-op alignment is needed before this leg can be classified.

## What exactness costs, and the one proof that is needed

Making the divide exact means a rail-width table that is a **proved worst-case bound** per tick, not a fitted one. A secondary question is whether 122 ticks always suffice.
- **The proof:** the convex-hull method of [sipa/safegcd-bounds](https://github.com/sipa/safegcd-bounds) applies, because every leapfrog branch is a linear map on (T, B). Propagating hulls per tick through the four steps and the W1 rule gives max |T|, |B| per tick, and therefore proven widths and a proven tick count.
- **Price (estimate, not measured):** each extra rail bit costs about +1 CCX per rail add (4 per tick) plus the barrel and swap work, roughly 6 CCX per tick per direction. That is ≈2.9k T per bit across both legs and directions (≈0.4%), plus 2 qubits at the peak. The proved bound fixes how many bits are needed. If it is 1–2 bits, exactness costs about 1% in score. A worst case far above the fitted envelope would cost more.

## hddivsteps: checked, not prototyped

- **Bound reproduced from data:** sipa's precomputed hull tables (`half_delta_output.txt`) give **591** iterations for all 0 ≤ g ≤ f ≤ p (plain divsteps: 725). External code was not executed; only the published table was read.
- **Toffoli estimate:** 591 halving steps against ≈607 average halvings for the leapfrog walk (113 ticks × ≈5.4). Per step, the leader's per-halving payload cost (≈577 T) plus a mandatory 256-wire conditional swap gives ≈591 × 833 ≈ **490k T per inversion, ≈1.4×**.
- **Width: decisive.** Two history bits per step means ≈**1,182 extra qubits** unless they are decoded. Decoding is the andigu route (≈4.0M T at 935 Q). hddivsteps is therefore not a near-term path under the 1,234/1,080 width caps.
