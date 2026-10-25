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
