# Theoretical DivPay-X at ~850k Toffoli

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
