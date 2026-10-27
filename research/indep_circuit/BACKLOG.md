# DivPay backlog with acceptance criteria

Code: [`src/point_add/`](src/point_add/). Design and history: [README.md](README.md).

**Baseline for every item.** The current code, measured with unit tests:
- division (or the inverse division): **1,369,781 T**, peak **1,963 Q** (`divide_and_multiply_256`);
- square: **137,491 T** (`sub_square_256`);
- full circuit estimate: **~2.88M T × 1,963 Q ≈ 5.65B**.
- Last official eval: **3,318,151 T × 2,139 Q = 7.10B** (phase 2b, 9024/9024 OK).

**Score exchange rate.** Score = T × Q, so one qubit is worth T/Q ≈ **1,470 T** at the baseline. Any trade of qubits for Toffoli (or back) is judged at this rate. Recompute it after each kept item.

---

## Definition of done (applies to every implementation item)

| # | Criterion | How to check |
|---|---|---|
| D1 | All unit tests pass with `bad 0, garbage 0x0, phase 0x0` | `cargo test --release -- --nocapture` in the challenge checkout with this `src/point_add/` |
| D2 | The 61-bit test still runs with **exact** comparators and the per-op reset check (no `R on nonzero`) | `divide_small_prime` |
| D3 | Both directions of the 256-bit division agree (forward = division, `emit_inverse` = multiplication) | `divide_and_multiply_256` prints `inverse false` and `inverse true` with equal T |
| D4 | Before/after numbers are recorded: division T, division peak Q, square T, estimated full T × Q | a row in the results table of README.md |
| D5 | **Keep rule:** keep the change only if the estimated full score (T × Q) drops, or a stated qubit target is met at no score loss | compare the D4 row with the previous row |
| D6 | **Exactness budget:** expected failures per 9024 shots λ ≤ 0.05 from all approximations together (step truncation, width table, window compares) | error budget of item R6; any new approximation states its own λ |
| D7 | An official eval at milestones (after items 2, 5, and every structural item): 9024/9024 OK, ancilla and phase garbage 0 | `build_circuit && eval_circuit` in an empty dir; **delete `ops.bin` afterwards (~1.1 GB)** |
| D8 | No generated streams or large files are committed (`ops.bin`, traces, dumps); generator scripts are | `git status` before commit |
| D9 | One commit per item; the message states the before/after T and Q | `git log` |

---

## Implementation items (ordered)

### I2: Mask-free masked add in the late payload steps
- **Goal:** remove the 256-wire mask `m = odd ∧ a` from the peak.
- **Rationale:** the peak is a late payload step: tape 900 + payload 512 + mask 256 + carries ~258 + ~35. The mask is the largest removable item.
- **Design:**
  - New `add_masked(odd, a, acc, cin)` in `arith.rs`. Per bit, with acc' = acc ⊕ c: c' = c ⊕ (acc'∧c) ⊕ (acc'∧odd∧a). The identity is checked exhaustively; see PLAN_next_steps.md.
  - Per bit: one AND(acc', c); one short-lived v = AND(odd, a); one AND(v, acc') into the same carry wire.
  - Erase: HMR plus a conditional CZ(acc', c) and a conditional CCZ(acc', odd, a). The CCZ executes only on m = 1 and counts as a Toffoli when it does.
  - Sum bit: CCX(odd, a_i, acc_i).
  - The w-compare in `payload_step_fast` needs only the top `WIN` = 40 mask bits: recompute those as temporary ANDs.
  - Apply from step t0 = first step where tape(t) + 512 + 516 + 35 exceeds tape(540) + 512 + 260 + 35. That is about 386; compute it exactly from `PACK` and the step count.
  - Builder: add `ccz_if`, and teach `emit_inverse` the erase pattern HMR → CZ_if → CCZ_if (same condition bit). Its reverse is the two-Toffoli compute (t = AND(acc', c); v = AND(odd, a); t ⊕= AND(v, acc'); erase v).
- **Research before coding:**
  - Price on paper: extra T = (steps − t0) × ~2.5 × 256 × 2 directions × 2 legs. Accept only if extra T / qubits saved < the exchange rate (1,470).
  - Check that no other register reaches the new peak, for example the carries of the ±p correction while the tape is full.
- **Acceptance criteria:**
  - D1–D9.
  - Division peak Q ≤ **1,710**.
  - Extra division T ≤ **+110k**.
  - Estimated full score ≤ **5.3B**.
  - The `emit_inverse` round trip of `add_masked` alone is the identity on 64 random shots (new unit test).
  - The average executed CCZ count of the erases is within 10% of half the bits (stats from the simulator).
- **Expected effect:** −256 Q, +~0.2M T, net ≈ −7%.
- **Risks:** a phase error in the CCZ fix-up. That shows up as phase ≠ 0 in D1, and the fix is a test of the erase in isolation first.

### I3: Unary-iteration lookup for tape packing
- **Goal:** cheaper `letters_from_code`. Today: 26 codes × 4-AND ladder ≈ 104 T per lookup, two lookups per group per direction.
- **Design:**
  - Babbush-style unary iteration over the 5-bit code with shared prefixes. About 27–32 Toffoli per lookup; erases by measurement.
  - The encode side, 6 small controlled constant adds, stays.
- **Acceptance criteria:**
  - D1–D6, D8–D9.
  - Packing cost per three steps (encode + lookup) ≤ **70 T**, from ~140 now.
  - Division T drops by ≥ **40k**.
  - New unit test: pack3 followed by unpack3 returns the 6 letter wires for all 27 valid patterns, and erases the code.
- **Expected effect:** −~58k T per division.

### I4: Five trits in eight bits
- **Goal:** a denser tape: 1.6 bits per step instead of 1.667.
- **Design:**
  - Groups of 5 steps, code = Σ 3^j·trit_j < 243, stored in 8 bits.
  - Encode with 10 controlled constant adds on 8 bits; decode with a unary-iteration lookup over 243 codes.
  - Partial last group stays unpacked, as now.
- **Research first:**
  - Count the Toffoli of the 243-entry lookup.
  - Compare against I3's 27-entry version. Accept if the extra T per qubit saved is below the exchange rate.
- **Acceptance criteria:**
  - D1–D9.
  - Tape qubits at the end of the forward walk ≤ **864**, from 900.
  - Score not worse than after I3.
  - Round-trip unit test over all 243 codes.
- **Expected effect:** −36 Q at roughly equal T.

### I5: Fine-tuning
- **I5a, steps 540 → 535:**
  - Research: rerun `research/novel/steps_tail.py 10000000 <seed>` on two seeds. Accept 535 only if P(steps > 535) ≤ 1e-6 per inversion (λ contribution ≤ 0.02).
  - Acceptance: measured tail recorded in README; D1–D9.
- **I5b, rail margin 3 → 1:**
  - Research: regenerate `rail_w.rs` with `research/novel/rail_widths.py 1000000 591 1`, then run `research/novel/width_check.py` on 1M fresh inputs (different seed).
  - Acceptance: 0 overflows in 1M, which gives a 95% upper bound of 3e-6 per inversion (λ ≤ 0.06). If the check fails, use margin 2.
- **I5c, 2δ register 12 → 11 bits:**
  - Research: the maximum |2δ| over 535 steps is below 2¹⁰. Prove it (|2δ| ≤ 2·steps + 1) or measure it.
  - Acceptance: D1.
- **Acceptance for I5 together:**
  - Division T −≥ **2%**, peak Q −≥ **8**.
  - Official eval (D7).

### I6: Carry-light constant adds in late steps (research first)
- **Goal:** after I2, the late-step peak is set by the ~258 Gidney carries of the ±p correction and the halving. Replace them by an adder that borrows dirty ancillas from the tape, which is idle during payload work.
- **Research tasks:**
  1. Write out the Gidney (2015) / Häner (2016) dirty-ancilla incrementer and the constant-adder cost for n = 257.
  2. Write ±p as add c′ (low 33 bits) plus a carry-controlled increment of bits 33–256.
  3. Price it: extra T per step × number of late steps, against the qubits saved.
- **Acceptance (research):** a priced note in this repo with the T and Q formula and a go/no-go against the exchange rate.
- **Acceptance (implementation, if go):**
  - D1–D9.
  - Peak Q −≥ **200**.
  - Score drops.
  - The borrowed tape qubits are verified unchanged after each add (unit test with random dirty contents).

---

## Research items (no code until the acceptance note exists)

### R1: Multi-halving "jump" ticks
- **Question:** merge each run of even divsteps into the following odd step (a barrel shift by e), so that the payload update and swap run once per tick instead of once per halving.
- **Known so far:** `research/novel/jump_divsteps.py` measures:
  - worst-case ticks: 317 at cap e ≤ 3, 303 at e ≤ 7;
  - letter cost: 3–4 bits per tick, 951 bits at e ≤ 3;
  - paper estimate: −~13% T, +~87 Q.
- **Tasks:**
  1. Design the payload fold for 2^−(e+1) mod p with pseudo-Mersenne Montgomery: m from v's low bits times c′^−1, subtract m·c′, add m·2²⁵⁶, rotate, and erase m by window compares.
  2. Price it per tick.
  3. Include the δ rule for merged ticks.
- **Acceptance:**
  - A priced design note showing the per-tick T and the tape bits.
  - Python reference of the merged walk with 1M inputs: 0 wrong inverses, worst tick count recorded.
  - A decision from the user, because the leader also uses a variant.

### R2: Rails without data-dependent swaps
- **Question:** can the f/g swap (w Fredkins per step, twice per division) be avoided? Options:
  - role tracking;
  - the two-add form (g −= f; f += g);
  - a swap-free divsteps variant.
- **Acceptance:** a cost table per step (Toffoli, extra qubits) for each option against today's 3w. Recommend only if it is ≥ 10% cheaper per step.

### R3: Tape below the fixed-length local floor
- **Known so far:**
  - Divsteps letters are ternary locally: 1.585 bits per step at the floor, 1.6–1.667 achievable.
  - Global information is 256 bits.
  - The redundancy is non-local (the rail pinned to p).
- **Question:** a δ-aware code: when δ′ > 1 the letter is determined ("even"). Is a fixed-width code with fewer bits per step possible, for example storing a trit only when δ′ < 1, with an address register?
- **Acceptance:**
  - Measured fraction of steps with δ′ < 1 (worst case over 1M inputs).
  - The cost of a data-dependent tape pointer (quantum-addressed write) per step.
  - Go only if the net score gain is ≥ 3%.

### R4: Proven width bounds (exactness without sampling)
- **Question:** replace the sampled `rail_w.rs` table (+3 margin) by a per-step bound derived from sipa's safegcd hull tables (half-delta, 256-bit), so that the width part of λ is exactly 0.
- **Acceptance:** a table generator that reads the published hull data, plus a comparison with the sampled table (Σw difference). The width-λ claim in README changes to "proven".

### R5: Window-compare error rate
- **Question:** the 40-bit window compares err only when both sides agree on the top 40 bits. Bound the total contribution to λ.
- **Tasks:**
  1. Count the window compares per point add.
  2. Measure, in a classical model, how often the compared values share 40 top bits on 1M random inputs.
  3. List the structured inputs that fail (small y, x = 1, y = p − 1) and their probability under the evaluator's input distribution.
- **Acceptance:** a λ estimate with method; window width chosen so that the compare λ ≤ 0.01.

### R6: Error budget
- **Question:** one table of every approximation and its λ per 9024 shots:
  - step truncation;
  - width table;
  - window compares;
  - zero cases (b = 0 handled exactly; y = 0 and dy = 0 inputs);
  - L or Tl ≥ p in the square (≈ 2⁻²²⁴).
- **Acceptance:** total λ ≤ 0.05, documented in README; each line with its source script.

### R7: Qubit floor of this architecture
- **Question:** what is the lowest peak this design can reach (tape + payload pair + carries) without recomputing the tape?
- **Tasks:**
  1. Write the per-step live-qubit profile from the builder (allocation trace over the division).
  2. Plot or tabulate the peak contributors.
- **Acceptance:** a live-qubit table at the 5 highest points of the division, with the owner of each register, and a stated floor with and without I2/I6. This is the basis for any further Q target.

### R8: Alternative walk with comparisons (Stein/Kaliski)
- **Question:** a binary GCD that compares |f| and |g| (a 40-bit window) and subtracts the smaller from the larger. Fewer steps per bit, no δ register, but a compare and swap per step.
- **Acceptance:**
  - Python reference: steps per inversion (mean and worst over 1M), letter alphabet per step, local preimage count (as in `lf_tail --branch`).
  - Priced cost per step against divsteps.
  - Recommend only if the estimated score is ≥ 10% better.

### R9: Exploiting average-executed Toffoli
- **Question:** which fix-ups and erases run conditioned on measurement outcomes (executed in ~½ of the shots)? Where can more work move behind such conditions without correctness risk? Candidates:
  - the CCZ fix-ups of I2;
  - the compare uncomputations.
- **Acceptance:** a list of candidates with expected average T saving and a unit test per candidate. Average executed T is checked in the simulator stats, not in the emitted count.

### R10: Square and coordinate phases
- **Question:** the square costs 137k T. Options:
  - textbook Karatsuba (also used by the leader; ask first);
  - a cheaper reduction (fold H·c with fewer adds);
  - removing the x −= L / Tl / u split.
- **Acceptance:** a priced option list. Implement only options that keep D5.

---

## Milestone targets

| Milestone | After | Target (estimate) | Check |
|---|---|---|---|
| M1 | I2 | ≤ 5.3B, Q ≤ 1,710 | official eval |
| M2 | I3–I5 | ≤ 4.9B, Q ≤ 1,670 | official eval |
| M3 | I6 (if go) | ≤ 4.5B, Q ≤ 1,470 | official eval |
| M4 | R1/R8 decision | below Google low-gate 2.99B | user decision before implementation |

The figures are estimates from the per-step anatomy in README.md. Each milestone replaces them by measured numbers.
