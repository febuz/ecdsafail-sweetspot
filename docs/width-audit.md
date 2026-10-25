# Width audit of the leader by classical simulation

[`analysis/live_width.py`](../analysis/live_width.py) re-simulates the leader's final `ops.bin` bit-parallel in Python (~45 s for 10.2M ops at 2,048 shots). It uses evaluator semantics: valid secp256k1 inputs, the condition stack, and random HMR/R outcomes. Validation: with `--fiat-shamir` it regenerates the evaluator's own 9,024 test points (SHAKE256 over the op stream) and passes **9,024/9,024**. The trusted `eval_circuit` reproduces the official 741,719.312 × 1,234 on the same `ops.bin`.

**Correctness off the evaluator's shot set.** On fresh random secp256k1 inputs the leader returns the wrong point on **10 of 4,096 shots** (≈0.24%: 2,044/2,048 at seed 1080, 2,042/2,048 at seed 3). At that rate, passing 9,024 independent shots has probability ≈ e⁻²² ≈ 3×10⁻¹⁰. The evaluator has zero tolerance, and its shots are a deterministic function of the op stream. The leader therefore passes because of *which* shots its op stream hashes to, not because it is exact. This is now confirmed directly; see [shot-set dependence](shot-set-dependence.md): reseeding with a no-op pair makes the evaluator fail 18–19 shots, and the source cites a "19.5 Lambda limit" and a ground `TAIL_NONCE`. Any redesign must either be exact or face the same dependence. Whether to accept that is a rules question, not a resource-estimation question. The evaluator scores width as max wire index + 1, so the question is how many wires *hold information* at each op.

| Probe | Result | Lever | Verdict |
|---|---:|---|---|
| Wires non-zero at the peak (op 1,190,586) | 1,234 of 1,234 | Wire renaming (interval colouring) | **0 qubits**: no idle-zero wires at the peak |
| Max over all ops of *distinct* live values (copies and complements merged) | 1,234 at op 4,528,829 | Copy-on-write fanout elimination | **0 qubits** at the binding op |
| GF(2) affine rank of the live state, 4,096 shots, two independent seeds | 1,218/1,234 (op 1.19M), 1,204/1,234 (op 4.42M), **1,233/1,234 (op 4.53M)** | CNOT-only (zero-Toffoli) compression | **≤1 qubit** at the binding op |
| Ops with ≥1,222 distinct live values | 183,556 ops in 4,549 ranges (~40 ops each) | Spike shaving | Thousands of short carry-scratch bursts on a ~1,200 plateau |
| Parked wires at the divide peak (idle ≥100k ops) | 170: 52 of input x, **118 ancillas in one block (~719–840)** | History compression | The leapfrog tape: the real width target |

The relations at ops 1.19M and 4.42M are real but sit off the binding op. They are parked *fanout copies*: seven copies of one bit on wires 239–245, four copies on 518/519/521/522 idle for ~600k ops, and 16 copies of wire 27 idle for 14k–25k ops. A copy-on-write pass would remove them for zero Toffolis, but it would only move the maximum once the other binding regions had been lowered too.

## Per-phase width (128 shots, sampled every 50 ops; phase bounds from the builder's `HEO_PHASE` markers, rescaled to post-pass indices)

| Phase | Toffoli share | Peak | Median | p90 | ≥1,200 | ≥1,150 | ≥1,100 | **≥1,080** | ≥1,050 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| divide | 47.2% | 1,234 | 1,131 | 1,211 | 17.2% | 43.2% | 59.5% | **62.1%** | 63.2% |
| square | 4.6% | 1,231* | 869 | 1,092 | 0.7% | 3.3% | 7.9% | **14.2%** | 18.5% |
| multiply | 48.1% | 1,234 | 1,136 | 1,213 | 17.9% | 44.1% | 64.2% | **64.2%** | 64.6% |

\*The exact maximum, 1,234 distinct values at op 4,528,829, lies in the square. The 50-op sampling missed it.

There are **three binding regions**: the divide walk, the square, and the multiply walk. The walk-history block (118 parked ancillas at the divide peak) is one component of one of them. At op 4.53M, by contrast, the parked wires are 128 bits of input y and no ancillas. Both walks sit above 1,080 for about two-thirds of their ops. Reaching the cap means lowering a broad plateau in both walks, not shaving bursts.

## Price per qubit: the bar a new mechanism must clear

| Reference | Toffolis per qubit removed |
|---|---:|
| Product break-even at the leader (T/Q) | ≈ 601 |
| Leader's own last qubit (`leapfrog.rs` C35 note: +543 T for 1,235 → 1,234) | ≈ 543 |
| **Average affordable for a record at 1,080 Q**: (847,482 − 741,719)/154 | **≈ 687** |
| Best published point at 1,080 Q: (1,837,665 − 741,719)/154 | ≈ 7,100 |
| This repo's 1,050 width retune: (~1,967,000 − 741,933)/184 | ≈ 6,660 |

Any new mechanism must remove walk-plateau qubits at about **10× lower Toffoli cost** than existing methods. Linear compression is ruled out (above). The candidates are non-linear and must be priced on this scale:
- decoding the walk tape from rail state, in the style of andigu's algebraic branch decoding;
- arithmetic (mod 2^k / mod p) relations between parked blocks, which GF(2) rank cannot see;
- a cheaper square, which only binds on 14% of its ops.
