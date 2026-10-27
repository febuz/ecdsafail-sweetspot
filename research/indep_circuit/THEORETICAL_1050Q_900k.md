# Paper design: ~1,050 qubits at ~830–900k Toffoli (Euclid shared-register path)

Calculator: [`theory_euclid_1050.py`](theory_euclid_1050.py). Measurements are in `research/`, on 20,000 random inputs. Nothing here is built.

Statuses:
- **M**: measured;
- **T**: textbook;
- **S**: speculative;
- **S!**: needs a new result.

## Measured basis
| Quantity | Value | Script |
|---|---|---|
| Radix-4 Euclid iterations (two quotient bits per iteration) | max **240**, mean 216 | `research/euclid_radix4.py` |
| Euclid steps per inversion | max 185, mean 150 | `research/shared_register.py` |
| Shared rails + tape peak, ideal Gauss–Kuzmin coding of quotients | max **524**, mean 515 | `research/euclid_radix4.py` |
| Same with Elias-gamma | max 551, mean 526 | `research/shared_register.py` |
| Divsteps for comparison (today's circuit) | 850–894 | `research/shared_register.py` |

**Qubit floor of this path:** shared register 524 + payload pair 512 + workspace. With ~14 workspace qubits (dirty-borrowed adders) that is **≈ 1,050**.

## Methods combined (from the technique lists)
| Method | Source | Role | Status |
|---|---|---|---|
| Proos–Zalka register sharing | Proos & Zalka 2003; arXiv 2604.02311 | rails and tape in one ~524–551-bit register | M (size), T (idea) |
| Classic Euclid with quotients | textbook | the information-tight walk (≈ 2n) | M |
| SRT radix-4 division with signed digits {−2..2}, digit chosen from a ~12-bit top window | Sweeney–Robertson–Tocher 1958 (hardware textbook) | two quotient bits per iteration, no full compare | T |
| Entropy / enumerative coding of quotients (Gauss–Kuzmin) | information theory | tape at the information floor | S (reversible block coder) |
| Gidney temporary ANDs with measurement-based erase | Gidney 2018 | adders at n−1 T, operand selection erased for free | T (built in DivPay) |
| Inline products in the carry chain (Q7 identity, checked) | this repo | operand select without a mask register | S |
| Deferred correction with Solinas folds | Solinas 1999; Montgomery / coset ideas | payload grows 2 bits per iteration, folded every 4 iterations | S |
| Dirty-borrowed adders | Häner–Roetteler–Svore 2016; Gidney 2015 | workspace 40 → ~14 qubits, at +50% on the replaced adds | S |
| Window compares (40 bits) | Gidney 2019 (approximate) | digit select, flags | T (built) |
| **Swap-free Euclid formulation** | open | step boundary ≤ 100 T per iteration instead of ~900 | **S!** (R17) |
| **Payload at ≤ 2n per iteration** | open | carry-save payload, one fold per 4 iterations | **S!** (R16) |

## Budget (per point add: two inversions at I = 240 iterations, square ~75k, coordinates ~4k)
| Design | T per iteration | T per division | T total | Q | Score |
|---|---|---|---|---|---|
| A: radix-4 SRT Euclid, known + S levers | 2,608 | 626k | 1.33M | 1,103 | 1.47B |
| B: + fused payload select (S) | 2,352 | 564k | 1.21M | 1,103 | 1.33B |
| C: + fused rails select (S) | 2,096 | 503k | 1.09M | 1,103 | 1.20B |
| D: + near-entropy coding, dirty workspace (S) | 2,360 | 566k | 1.21M | **1,050** | 1.27B |
| **E: + swap-free boundary ≤ 100 T (S!)** | **1,564** | **375k** | **0.83M** | **1,050** | **0.87B** |
| F: + payload ≤ 2n per iteration (S!) | 1,372 | 329k | 0.74M | 1,050 | 0.77B |

## Where the 900k comes from
- The **step boundary** is the biggest cost item. A Euclid step ends at a data-dependent iteration, so every iteration carries a conditional swap of rails and payload plus a realignment: ~900 T. **Design E only works if a formulation exists without these swaps.**
- Rails per pass: ~2w + 50 per iteration with fused select, w ≈ 128 on average; both passes are needed.
- Payload: ~2.25n plus a dirty penalty per iteration with deferred correction.
- Square ~75k (backlog R10) and coordinates ~4k.

## Update from the R16–R18 harness (rnd/, laptop runs)
- **Radix-4 iterations are 283 at the maximum** (mean 259), not 240. At equal per-iteration cost, design E becomes ≈ 0.95M T and F ≈ 0.84M T.
- **Codes must work at quotient level.** Elias-gamma on quotients gives a shared peak of 544; coding per radix-4 digit gives ~900.
- **Removing swaps by fixed role parity doubles the iterations.** R17 needs a different formulation.
- **Lazy payload reduction costs only +5 bits** with a fold every 16 iterations.

## Assessment
- **1,050 qubits close on paper** with measured inputs (524 + 512 + 14). It needs near-entropy coding (S) and dirty-borrowed workspace (S).
- **~830k T needs one new result (S!):** a Euclid formulation without conditional swaps at the step boundaries. Design F (~740k) needs a second one: payload ≤ 2n per iteration.
- **If E holds, the paper score is ~0.87B.** That would be below the leader (0.915B) at 184 fewer qubits. This depends entirely on R16–R18; the uncertainty is high, so it is a research target, not a promise.
