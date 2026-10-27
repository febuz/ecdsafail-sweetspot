# DivPay: next efficiency steps (backlog, research before test)

> Status 2026-10-27: items 0 and 1 are done in the code here (division 1.370M T, Q 1,963 in unit tests). Item 0's official eval was not run: the local disk was full, and execution moves to a machine with more disk. Continue from item 2.

## Context
The user asked for a strictly own, low-qubit circuit (no leader techniques), built step by step.

**Status:**
- Branch `indep-divpay`, worktree `/private/tmp/indep`.
- Last official eval (phase 2b): **3.318M T × 2,139 Q = 7.10B**, 9024/9024 OK.
- Uncommitted since then: compare-first `mod_add`, 3-trit tape packing, `payload_step_fast`.
  - Division unit test: 1.418M T, Q 1,963.
  - Estimate: ~2.98M T × 1,963 ≈ **5.85B**.

**Where the cost sits now** (per division, from the step anatomy in `divide.rs`):

| Component | Toffoli | Share |
|---|---|---|
| Payload, steps ≥64 (≈1,450 T/step) | ~689k | 59% with the next row |
| First 64 safe steps (≈2,300 T/step) | ~147k | |
| Rails, 2 passes (3w + D per step) | ~472k | 33% |
| Tape packing | ~50k | |

**Peak qubits** occur in a late payload step:

| Item | Qubits |
|---|---|
| Tape | 900 |
| a, b | 512 |
| Mask `m` | 256 |
| Gidney carries | ~258 |
| Rest | ~35 |

**Goal of this round:**
- Remove the worst inefficiencies one at a time.
- Measure each one before and after.
- Never break exactness: no grinding, λ ≪ 1.

## Research already done (read-only checks)
- **T4 compare identity, checked exhaustively on 6 bits:** w = carry(r + ¬m + (¬swap)) equals swap ? [r>m] : [r≥m]. This makes the merged payload step exact also when b = 0 at the first swap, so the 64 "safe" steps are unnecessary.
- **Q7 carry identity, checked over all 16 cases:** with acc' = acc ⊕ c, c' = c ⊕ (acc'∧c) ⊕ (acc'∧odd∧a) equals MAJ(acc, odd∧a, c). A masked add can therefore run without the 256-wire mask register:
  - per bit: 1 AND(acc',c), 1 short-lived v = AND(odd,a), 1 AND(v,acc') into the same carry wire;
  - erase by measurement plus a conditional CZ and CCZ, where the CCZ executes in ~½ of the shots;
  - sum bit: CCX(odd, a_i, acc_i).
  - Cost ≈ +2.5n T per masked add, −256 Q.

## Backlog (in order; each item: implement → unit tests → measure → keep only if the score drops)
0. **Bank the current state.** Commit FAST_PAYLOAD/PACK/compare-first, run the official eval and note T, Q and score.
1. **T4: fast payload for every step.** Replace the `cin = 1` window compare in `payload_step_fast` (`ge_flag`) with a compare whose carry-in is ¬swap.
   - Add `ge_flag_cin(a, acc, cin_qubit, flag)` in `arith.rs`, reusing `carry_flag`.
   - Delete the `SAFE_STEPS` path, `cmod_neg_safe` usage and `payload_step`.
   - Expected: −~108k T total, simpler code.
2. **Q7: mask-free masked add in the payload.**
   - New `add_masked(odd, a, acc, cin)` in `arith.rs`.
   - Recompute only the top-40 mask bits for the w compare. This is the ge_flag window, so `WIN` is reused.
   - Builder: add `ccz_if` and extend `emit_inverse` in `builder.rs` to reverse the pattern HMR + CZ_if + CCZ_if (one erase) into its two-Toffoli compute.
   - Apply only to the late steps where the peak binds (t ≥ t0, with t0 chosen from the tape-growth formula, ≈386).
   - Expected: −256 Q, +~0.2M T, net ≈ −7% score.
3. **T5: unary-iteration lookup in `letters_from_code`.** Share AND prefixes over the 27 codes instead of a 4-AND ladder per code. Expected −~58k T.
4. **Q3: 5 trits in 8 bits** (243 codes, unary-iteration lookup). Expected −36 Q at roughly equal T. Keep only if the score drops.
5. **Fine-tuning:**
   - STEPS 540 → 535 (0 of 1M samples > 535);
   - rail margin 3 → 1 (regenerate `rail_w.rs` with `research/novel/rail_widths.py`, 200k samples);
   - D register 12 → 11 bits.
   - Expected −~2% T, −~10 Q.
6. **Q2 (research first): carry-light constant adds in late steps.** Use a dirty-borrowed-ancilla incrementer (Gidney 2015) for the ±p correction and the halving, borrowing tape qubits.
   - Price it on paper before building: exchange rate now ≈ 1,480 T per qubit; worth it only below that.

After 1–5, expected ≈ **2.87M T × ~1,660 Q ≈ 4.8B**. That is still above Google (2.99B). Ask the user before taking structural steps beyond this, because the largest remaining lever (multi-halving "jump" ticks, −~13% T) also appears in the leader.

## Critical files
- `/private/tmp/indep/src/point_add/divide.rs`: payload steps, tape packing, divide loop.
- `/private/tmp/indep/src/point_add/arith.rs`: `add`, `carry_flag`, `ge_flag`, `const_chain`, `mod_add`, `mod_halve`.
- `/private/tmp/indep/src/point_add/builder.rs`: `and_compute` / `and_uncompute`, `emit_inverse`.
- `/private/tmp/indep/src/point_add/rail_w.rs` and `mod.rs` (STEPS).
- Measurement scripts: `~/ecdsafail-sweetspot/research/novel/{rail_widths.py,steps_tail.py}`.

## Verification (every item)
1. `cargo test --release -- --nocapture` in `/private/tmp/indep`. All three tests must show bad 0, garbage 0, phase 0:
   - `divide_small_prime`: 61-bit, exact compares, per-op R check;
   - `divide_and_multiply_256`: 64 random shots, both directions;
   - `sub_square_256`.
   Note the Toffoli and qubit counts of the test as the before/after measure.
2. After items 0, 2 and 5: full build plus the official `eval_circuit` (9024 shots) in a fresh scratchpad dir. Record T, Q and score in a backlog table in `ecdsafail-sweetspot/docs/novel-design.md`, and commit on `indep-divpay`.
3. Never submit to ecdsa.fail unless the user asks.
