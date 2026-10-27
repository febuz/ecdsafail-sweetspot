# DivPay: an independent secp256k1 point-add circuit

This is our own circuit for the ecdsa.fail challenge. It is built from textbook parts plus techniques from non-leader work, and uses no leader constructs. Source: [`src/point_add/`](src/point_add/), a drop-in replacement for the harness's editable directory. The next steps are in [`PLAN_next_steps.md`](PLAN_next_steps.md).

No op streams (`ops.bin`, 1–2 GB each) or other large generated files are in this repo. Every number below can be regenerated with the commands under "How to run".

## Design (theory)

**Point add, in place:**
1. x −= ox, y −= oy
2. y ← y / x (divsteps division; x is kept)
3. x += 3ox − y²
4. y ← y · x (the division run backwards)
5. y −= oy, x ← ox − x

**Division** (`divide.rs`): half-delta divsteps (Bernstein–Yang).
- **Step count:** 540 steps. The proven bound is 591; 0 of 1.2M random inputs needed more than 537.
- **Rails (f, g):** start as (p, x). Two's complement, shrinking per step to a width table (`rail_w.rs`: the maximum over 200k inputs plus 3 bits).
- **2δ:** a 12-bit register.
- **Payload (a, b):** starts as (0, y), with a·d ≡ f·y and b·d ≡ g·y (mod p). It ends at ±y/d and is put back on the y wires.
- **Tape:** ternary letters (odd, swap), three steps packed into 5 bits.
- **Reverse rails pass:** erases the tape and restores x on its original wires.

**Arithmetic** (`arith.rs`):
- Gidney adders (temporary ANDs, erased by X-measurement).
- Constant adds without constant registers: AND/OR carries; ±p written as ∓(2²⁵⁶ + 2³² + 977), which has 8 set bits.
- 40-bit top-window comparators, exact on equality.
- Compare-first modular add; modular halving by +p and a SWAP rotation.

**Merged payload step** (`payload_step_fast`):
- s = σ·b + odd·a in one signed add, then one ±p correction.
- The flags are erased with one compare with carry-in ¬swap (strict on a swap, so the b = 0 case at the first swap is exact).

**Square** (`square.rs`): symmetric schoolbook rows plus Solinas reduction (p = 2²⁵⁶ − c).

**Inverse blocks** (`builder.rs`): `emit_inverse` turns measurement erases back into Toffoli computes and the other way round, so the multiply leg costs the same as the division.

## Measured results

Official `eval_circuit` runs use 9024 Fiat-Shamir shots and no grinding. The rest are unit tests.

| Version | Toffoli | Qubits | Score | Status |
|---|---|---|---|---|
| Phase 1: textbook, Cuccaro adders | 10,316,501 | 2,741 | 28.3B | official, 9024/9024 OK |
| 2a: shrinking rails, Gidney adders, constant adders without registers | 5,617,343 | 2,241 | 12.6B | official, 9024/9024 OK |
| 2b: window compares, 540 steps, measurement-erased masks, schoolbook square | 3,318,151 | 2,139 | 7.10B | official, 9024/9024 OK |
| 2c: compare-first mod_add, 3-trit tape packing, merged payload | ~2.98M est. | 1,963 | ~5.85B | unit tests; division 1.418M T |
| 2d: carry-in ¬swap compare, fast step for all 540 steps | ~2.88M est. | 1,963 | ~5.65B | unit tests; division 1.370M T (current code) |

**References:**
- leader: 741,645 × 1,234 = 0.915B (approximate, ground);
- Google low-gate: 2.1M × 1,425 = 2.99B;
- Google low-qubit: 2.7M × 1,175 = 3.17B.

## Where the cost sits (per division, current code)

| Part | Toffoli | Note |
|---|---|---|
| Payload | ~1,450 T × 540 ≈ 0.78M | cswap 256, mask 256, add 258, ±p correction ~258, compares ~120, halving ~300 |
| Rails, forward + reverse | ~0.47M | per step: cswap w + mask w + add w + 2δ update; Σw ≈ 75k |
| Tape packing | ~0.05M | |

**Peak qubits, at a late step:**

| Item | Qubits |
|---|---|
| Tape | 900 |
| Payload | 512 |
| Mask | 256 |
| Gidney carries | ~258 |
| Rest | ~35 |

## Backlog (see PLAN_next_steps.md)

| # | Step | Expected effect |
|---|---|---|
| 0, 1 | Carry-in ¬swap compare, fast step for all steps | **done**: −48k T per division |
| 2 | Mask-free masked add in late steps | −256 Q, +~0.2M T, net ≈ −7% |
| 3 | Unary-iteration lookup for tape packing | −~58k T |
| 4 | 5 trits in 8 bits | −36 Q |
| 5 | 535 steps, rail margin 1, 2δ in 11 bits | −~2% T, −~10 Q |
| 6 | Carry-light constant adds via a dirty-ancilla incrementer | research first; only if < 1,480 T per qubit |

**Expected after 2–5:** ≈ 2.87M T × ~1,660 Q ≈ 4.8B, still above Google.

**Structural options after that** (decide first):
- Multi-halving "jump" ticks: −13% T. The leader also uses a variant of this.
- Late-step low-ancilla adders.

## How to run (on a machine with enough disk; each `ops.bin` is ~1.1 GB)

1. Check out the challenge repo at the initial circuit, commit `e8ce2c9` (parent of the first accepted submission):
   ```
   git clone https://github.com/gpsanant/ecdsafail-challenge && cd ecdsafail-challenge && git checkout e8ce2c9
   ```
2. Replace the contents of `src/point_add/` with this directory's `src/point_add/*.rs`.
3. Run the unit tests: `cargo test --release -- --nocapture`. They cover the 61-bit division (exact, per-op reset check), the 256-bit division and multiply (64 shots each), and the square. Each must report bad 0, garbage 0, phase 0.
4. Build and evaluate in an empty directory:
   ```
   target/release/build_circuit && target/release/eval_circuit
   ```
   Then delete `ops.bin`.

The local history is on branch `indep-divpay` in `~/ecdsafail` (worktree `/private/tmp/indep`). Nothing has been submitted to ecdsa.fail.

## Supporting analysis in this repo
- `research/novel/`: divsteps simulation (`divsteps_sim.py`), step tail (`steps_tail.py`), rail widths (`rail_widths.py`, `width_check.py`), jump-tick count (`jump_divsteps.py`), cost models (`textbook_design.py`, `stack.py`) and the technique workbook builder.
- `docs/novel-design.md`, `docs/technieken_analyse.xlsx`: technique catalogue and the first DivPay cost model. The model's 2.95–3.06B was optimistic: it left out the payload mask and per-step corrections, as the measured table above shows.
