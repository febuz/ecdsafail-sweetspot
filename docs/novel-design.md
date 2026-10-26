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

| Variant | Toffoli | Qubits | Score | vs Google low-gate (2.99B) |
|---|---|---|---|---|
| T6: textbook + generic modern primitives | 2.09M | 1,414 | **2.95B** | 0.986× (−1.4%) |
| Strict: no technique the leader uses | 4.09M | 1,487 | 6.09B | 2.03× |
| Leader (approximate, ground) | 0.74M | 1,234 | 0.915B | 0.31× |

**How T6 beats Google, and by how much.** T6 beats both Google points, but only because it uses four generic primitives that the leader also uses:
- window comparators;
- chunked adders;
- Solinas reduction;
- measurement-based uncompute.

The 1.4% margin over the low-gate point is smaller than the model's uncertainty. The chunked-adder overhead and the comparator costs are estimates.

**Strictly leader-free, it does not beat Google.** It is about 2× worse.

**Exactness.** Both variants are effectively exact: λ ≈ 0.02 from truncating at 535 steps; strict uses the proven 591. Neither needs grinding.
