# DivPay: a point add without the leader's constructs (2026-10-26)

**Workbook:** [technieken_analyse.xlsx](technieken_analyse.xlsx). It has 9 sheets and 6,073 formulas, recalculated with 0 errors. It contains:
- 45 techniques used across all solutions (from 154 submission notes plus the leader's source);
- 36 unused techniques, including 2024–2026 work;
- 35 textbook methods, from 2-qubit gates to 256-bit blocks;
- a weight model, Gower similarity, the design, a comparison and the milestones.

Code is in [`research/novel/`](../research/novel/).

## Design

| Part | Choice | Status |
|---|---|---|
| Structure | Roetteler-style in place: division walk on dx, square, multiply walk on d′ | textbook |
| Inversion | half-delta divsteps (Bernstein–Yang), fixed step count, ternary letters | checked: 3000/3000 inverses correct; max 535 steps on 1,000,000 inputs (proven bound 591) |
| Rails | per step: controlled swap + sign-controlled add/sub on the envelope width | envelope measured (median + 7 bits) |
| Payload | (u, v) mod p: swap, add/sub, mod-p correction, modular halving | textbook primitives |
| Transcript | 17 trits packed in 27 bits | radix packing |
| Square | schoolbook n²/2 + reduction | textbook |

## Result (cost model, not built)

| Variant | Toffoli | Qubits | Score | vs Google low-gate (2.99B) | vs Google low-qubit (3.17B) |
|---|---|---|---|---|---|
| T6: textbook + generic modern primitives | 2.16M | 1,418 | **3.06B** | 1.024× (+2.4%) | 0.965× (−3.5%) |
| Strict: none of the leader's constructs (G-ids) | 4.71M | 1,491 | 7.02B | 2.35× | 2.2× |
| Leader (approximate, ground) | 0.74M | 1,234 | 0.915B | 0.31× | 0.29× |

**Strict definition.** No construct from the Gebruikt catalog (G-ids). Elementary gates, adders and comparators are shared by every circuit and stay allowed.

**Strictly leader-free does not beat Google.** It is about 2.35× worse.

**T6 is about level with Google.**
- It uses generic primitives that the leader also uses: window comparators, chunked adders, Solinas reduction and measurement-based uncompute.
- It beats the low-qubit point by ~3.5%. Against the low-gate point it sits within model error, just above (+2.4%).
- A first version priced the controlled ±p constant adds at n T without carry ancillas and showed 2.95B. That was corrected.

**Exactness.** No grinding is needed. The step-count truncation at 535 shows 0 failures in 10⁶ inputs: 95% upper bound ~3×10⁻⁶ per inversion, so λ ≲ 0.05. Strict uses the proven 591. The rail-width check (`width_check.py`, 200,000 inputs) found single steps up to 8 bits above the 1,500-sample envelope. The rails are now costed on the 200k envelope + 2 bits per step; a proven per-step bound (sipa hull) would make the widths exact.

**Weighting caveats.**
- The weighting sheet is a *suitability* ranking. With most T-effects at 0, maturity, simplicity and gate-set compatibility decide the order, so the top ranks are elementary primitives, not levers.
- Gower novelty barely discriminates: 14 mostly binary features, and the unused inversion methods all land near the same neighbour.


## Built circuit

The DivPay circuit itself, with measured official results, the backlog and how to run it, is in [`research/indep_circuit/`](../research/indep_circuit/README.md).
