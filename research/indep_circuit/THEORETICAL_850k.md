# Theoretical DivPay-X at ~850k Toffoli (and a speculative 1,050-qubit variant)

This is a paper design. Nothing below the "today" row is built or tested. The calculator is [`theory_850k.py`](theory_850k.py), which states every assumption and its status:
- **M**: measured in this repo;
- **T**: textbook cost formula;
- **S**: speculative, needs research;
- **L**: also used by the leader (needs the user's OK).

Model calibration: the "today" row gives 2.76M T, against ~2.88M estimated from the unit tests (−4%).

## Stack

| # | Lever (status) | Rails/division | Payload/division | T total | Q | Score |
|---|---|---|---|---|---|---|
| 0 | today, DivPay 2d (M) | 477k | 783k | 2.76M | 1,966 | 5.43B |
| 1 | backlog I2–I5 (T/M) | 467k | 875k | 2.88M | 1,666 | 4.80B |
| 2 | jump ticks: merged halvings, 305 ticks, one Montgomery fold per tick (S/L, R1) | 351k | 387k | 1.65M | 1,725 | 2.85B |
| 3 | swap-free fixed role schedule (S/L, R2) | 269k | 302k | 1.32M | 1,725 | 2.27B |
| 4 | deferred ±p correction: padded redundant payload, fold every 8 ticks (S) | 269k | 200k | 1.11M | 1,773 | 1.97B |
| 5 | cheaper reverse rails pass, 2.5w per tick (S, R3/R5) | 229k | 200k | 1.03M | 1,773 | 1.83B |
| 6 | leaner square, ~75k (T) | 229k | 200k | 0.96M | 1,773 | 1.70B |
| 7 | add and fold merged in one carry chain (carry-save layer, ~1.6n), tape 3 ticks per 8 bits (S) | 229k | 166k | 0.89M | 1,671 | 1.49B |
| **9** | **deferred rail shifts: one barrel per two ticks, 2.25w per tick (S)** | **208k** | **166k** | **0.85M** | **1,671** | **1.42B** |
| 8 (alt.) | step 7 + chunked carries in late ticks (T): fewer qubits, more T | 229k | 194k | 0.95M | 1,453 | 1.38B |

## What has to hold for 850k
1. **Jump ticks (R1).** 305 ticks (worst case ≤ 317 measured at e ≤ 3) instead of 540 steps, with one modular fold per tick.
   - Status: a priced design is still missing.
   - The leader uses a variant of this.
2. **No data-dependent swaps (R2).** A fixed role schedule on rails and payload.
   - Status: open. It is also the core of the leader's walk.
3. **Deferred correction.** The payload lives in a padded redundant range and is reduced only every ~8 ticks.
   - Needs: a proof that halving and folding stay in range without per-tick compares.
4. **A reverse rails pass at 2.5w per tick, and deferred shifts at 2.25w.**
   - Speculative. Today it costs 3w; the barrel stages are Fredkins and cannot be erased by measurement.
5. **Payload add and Montgomery fold in a single carry chain** (3-operand, carry-save): ~1.6n per tick instead of 2n.
6. **Square ~75k**, from 137k today.

## Assessment
- **850k is reachable on paper only.** It needs **all** speculative levers at once. Their combined risk is high: each S row needs its own proof and implementation (BACKLOG R1–R5 plus new items for 3, 4, 5).
- **The two biggest levers (rows 2 and 3) are the core ideas of the leader's walk.** The leader's real circuit is at 742k T. A theoretical 850k design therefore lands in the same family; independently derived, but not structurally different.
- **The qubits stay ~1,450–1,770 in this model.** At 850k T the score is ~1.4B: below Google (2.99B and 3.17B), above the leader (0.915B).
- **Realistic without speculative levers** (rows 1, 6 and the textbook part of 8): ~2.8M T, 4.5–4.8B.

---

# Speculative qubit levers down to ~1,050 Q

Calculator: [`theory_1050q.py`](theory_1050q.py). It starts from row 9 above (848,591 T, 1,671 Q). The peak sits at the end of the forward walk:

| Item | Qubits |
|---|---|
| Tape | 813 |
| Payload pair | 560 |
| Carries | 258 |
| Rest | 40 |

Statuses: **T** textbook, **S** speculative, **S!** needs a new result.

| Step | Lever (status) | T | Q | Score |
|---|---|---|---|---|
| 9 | 850k paper design | 0.85M | 1,671 | 1.42B |
| Q1 | chunked carries, blocks of 32 (T) | 0.91M | 1,453 | 1.32B |
| Q2 | payload guard bits 24 → 6 (S: range proof for the deferred correction) | 0.91M | 1,417 | 1.28B |
| Q3 | block arithmetic coding of the tick letters, ~2.3 bits/tick (S: letter entropy still to be measured) | 0.94M | 1,306 | **1.23B** |
| Q4 | transposed integer cofactors built in the reverse pass, with no payload during the forward walk; end: exact 2-adic erase of m11 and an in-place product y·m12·2^−K (S) | 1.82M | 1,108 | 2.02B |
| Q5 | in-place end product with one extra register, borrowing rail wires dirty (S!) | 1.82M | 1,058 | 1.93B |
| **Q6** | **carry blocks of 24, fewer loose ancillas (T/S)** | **1.83M** | **1,042** | **1.91B** |

## How the 1,050-qubit path works
1. **The payload pair leaves the walk peak (Q4).**
   - The forward walk only writes the tape.
   - During the reverse rails pass, which consumes the tape, the row vector e₁ᵀ·M_S⋯M₁ is built as integers in reverse step order. It grows as the tape shrinks, so the two share the room.
   - At the end, the inverse is y·m12·2^−K mod p, with the constant 2^−K known classically.
2. **The cost is an in-place modular multiplication at the end** (compute z = y·u, erase y with z·d·2^−K): about +0.9M T per point add. Q5 additionally needs an in-place product with one extra register (S!), otherwise the end phase peaks at ~1,108.
3. **The tape is compressed below the fixed-length code (Q3),** and the carries are chunked (Q1, Q6).

## Correction (2026-10-27)
- **Q4 is under-priced.** After the end product, the integer cofactor u (and m11) is garbage. Erasing it needs u recomputed from d, which is one more walk (forward rails with tape, then the reverse pass that un-builds the row vector). That adds ≈ +0.3M T per division.
- **Lazy Montgomery products** (bit-serial, z < 2p kept without per-bit reduction, about 2n + 40 T per bit) bring the end products from ~230k to ~141k each.
- **Corrected Q4–Q6 path:** ≈ 2.0–2.3M T at ~1,042 Q, which is 2.1–2.4B.
- **The earlier claim "the best score is at ~1,300 qubits" is withdrawn.** It only held for the levers in this table, and the next section shows a lever that changes the low-qubit picture.

## New measurement: Proos–Zalka register sharing with a Euclid walk (R11)
`research/shared_register.py` and `research/quotient_bits.py`, 20,000 random inputs. For each walk family, the peak of bits(f) + bits(g) + tape written so far, when rails and tape share one register:

| Walk | Shared rails + tape peak (mean) | q99.99 | Max | Steps or iterations |
|---|---|---|---|---|
| Classic Euclid, Elias-gamma quotients | **526** | 547 | **550** | 150 steps (max 185); bit-serial: **354 iterations max** (mean 337) |
| Nearest-integer Euclid | 649 | 687 | 691 | 105 steps |
| Divsteps, ideal ternary (log₂ 3) | 850 | 850 | 850 | 535 |
| Divsteps, 3 trits in 5 bits (today) | 894 | 894 | 894 | 535 |

**Classic Euclid is information-tight: about 2n.** With rails and tape in one shared register (~550 bits), the forward payload pair (512) and ~70 workspace, the division peaks at ≈ **1,130 Q**. That is without an end product and without an extra walk; the output lands on y as today.

**Cost** (estimate, bit-serial Euclid, 354 iterations per inversion). Per iteration:
- compare: a window of ~40, or full w;
- conditional subtract on the rails: ~w;
- conditional shift of the shared register and the divisor alignment: ~550 Fredkins;
- payload a −= b·2^k: halving (n + 40) plus a conditional modular subtract (2n + 80), ≈ 890.

So about 0.32M T per rails pass (×2) plus 0.31M T payload, ≈ 0.95M T per division, ≈ **2.05M T per point add at ~1,130 Q (≈ 2.3B)**, before any of the speculative T levers. Several of the 850k levers (deferred correction, merged add and fold, chunked carries) apply here too.

## Low-qubit options compared (paper estimates)

| Path | T | Q | Score | Main open question |
|---|---|---|---|---|
| Q3 (forward divsteps, block-coded letters) | 0.94M | 1,306 | 1.23B | letter entropy ≤ 2.3 b/tick (R3) |
| Bit-serial Euclid with Proos–Zalka sharing | ~2.05M | ~1,130 | ~2.3B | cheap data-dependent shift of the shared register; window compare exactness |
| Same + speculative T levers (deferred correction, merged add and fold, lazy payload) | ~1.3–1.5M (S) | ~1,100 | ~1.5B (S) | all of the above |
| Same + workspace on dirty borrowed wires (Häner 2016) | ~1.5–1.7M (S) | ~1,060 | ~1.7B (S) | dirty-ancilla adders cost 2–4× T |
| Transposed integer cofactors (Q4–Q6, corrected) | 2.0–2.3M | 1,042 | 2.1–2.4B | in-place end product (S!), extra walk |

## Assessment
- **No path has been shown to give the lowest score at ~1,300 qubits.** The Euclid sharing path puts ~1,100 Q within reach at a T that is not yet pinned down (1.3–2.05M). Measured so far: the information-tight register (550 bits max).
- **For ~1,050 Q, the most promising route** is bit-serial Euclid with register sharing and a forward payload, plus low-workspace (dirty or conditionally clean) adders. The open item is the T cost of the data-dependent register shift. See BACKLOG R11–R15.
