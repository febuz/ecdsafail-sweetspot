# Experiments and exclusions

All experiments below are local. None is a validated 1,080-qubit / 850,000-Toffoli point-addition result.

| Experiment | Evidence | Decision |
| --- | --- | --- |
| Q999 source retuned to Q1050 | Builder expected count 1,966,959.5 after truth/wide passes; independent evaluator not reached | Keep as unvalidated width exploration |
| Q885 with existing wide/conditional passes | Wide pass saved 23 expected Toffolis; slow conditional pass stopped before completion | No benchmark claim |
| Sparse quadratic measured cleanup | 160 coherent statevector cases, all 512 outcome branches pass | Valid local component; full-circuit integration unresolved |
| Rec2 phase replay with vented fallback | No positive analytical saving for widths 1–257 and scratch 0–128 | Exclude |
| Rec2 recursive chunks as adding leaves | No positive analytical saving over the existing cost grammar on the same grid | Exclude |
| Provenance-tracked bilinear rank lowering | Demonstration compute 5 → 2 CCX; zero-CCX measured cleanup; 132 coherent branches and 512 matrix reconstructions pass | Valid local component; full GF(p) lowering and integration unresolved |

The two cost screens reproduce the recurrence in gnuchev's public SKY-COF source [d7f4e84](https://github.com/Layr-Labs/ecdsafail-challenge/commit/d7f4e842c90df365b5c08a5e25b326aba53894f0), `skycof/adder.rs`, and add one proposed leaf option at a time. Their zero saving is a scoped result for that grammar, not a lower bound on reversible addition or the complete target. Reproduce with:

```bash
python3 analysis/carry_plan_screen.py
```

The next useful complete-circuit experiment must remove long-lived walk state as well as carry scratch: the leader's active state alone reaches 1,197 qubits. A teleportation routing change cannot erase that logical information. No carry precision or guard bits have been removed in this repository.
| Local rewrite rules on the leader's final `ops.bin` (10.2M ops) | 0 hits at windows 256 and 100k; identical reusable products bracketed 79–13,871 (≤1.8% of T); 68% of CCX targets already HMR-cleaned | Excluded as a Toffoli lever; see [programmatic-efficiencies](programmatic-efficiencies.md) |
| hddivsteps (sipa hull bound 591 for secp256k1) | Worst-case bound vs. the leapfrog's empirical average envelope (~490–850 halvings); not like-for-like | Unresolved; hull method retained as an envelope-proof tool |
| Algebraic branch decoding of the leapfrog tape (andigu-style) | 99.3–100% of letters ambiguous under the width envelope; 5.75 bits/tick of fresh entropy | Does not apply to leapfrog; closed |
| Drop one payload register (P_i = λ·R_i) | Multiplicative relation; rebuilding needs a modular multiply/divide per tick; park tie already used by the leader | Closed |
| Reseed the leader with a no-op `X;X` pair (3 variants) | Evaluator fails 18–19/9,024 each time; fresh-input failure ≈0.21%; source cites "19.5 Lambda limit" and `TAIL_NONCE` | Leader is λ≈19.5 approximate + nonce-ground; all savings must be priced against an exact baseline |
| Prove the leader's 830 `lane3_sigcut` edits (bounded-ANF dataflow) | 375 proved; 455 rest on forward/reverse walk reversibility; leader vs no-post-edit rebuild fail on the identical 8/4,096 inputs; post-edits save 1,334 T | Failures are in the core walks, not the cuts |
| Failure localization by λ snapshot | 44% divide walk, 0% square, 56% multiply walk (32 failing shots) | Exactness work belongs in the walks |
| Variant F: real-circuit rail traces, divide leg | Payload invariant P = ±λR holds on all passing shots; 4/4 divide-failing shots have runs of zero rail-width margin vs 2 isolated events in 4,088 passing shots | Divide failures = fitted width envelope one bit short; a proved (hull) width table is the needed proof |
| Variant F, multiply leg | Builder/stream index misalignment (SQTOP +480, pp_simplify −22) | Unresolved; needs marker alignment |
| hddivsteps (sipa table: 591 steps) | ≈1.4× Toffoli (model) but ≈1,182 extra history qubits | Not a near-term path under the width cap |
