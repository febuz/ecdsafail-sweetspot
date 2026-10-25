# Width audit of the leader by classical simulation

[`analysis/live_width.py`](../analysis/live_width.py) re-simulates the leader's final `ops.bin` bit-parallel in Python (~45 s for 10.2M ops at 2,048 shots). It uses evaluator semantics: valid secp256k1 inputs, the condition stack, and random HMR/R outcomes. It reproduces the evaluator's results: **2,042–2,044 of 2,048 shots are correct**, so the leader is an approximate circuit, as its expected-Toffoli accounting implies. The evaluator scores width as max wire index + 1, so the question is how many wires *hold information* at each op.

| Probe | Result | Lever | Verdict |
|---|---:|---|---|
| Wires non-zero at the peak (op 1,190,586) | 1,234 of 1,234 | Wire renaming (interval colouring) | **0 qubits**: no idle-zero wires at the peak |
| Max over all ops of *distinct* live values (copies and complements merged) | 1,234 at op 4,528,829 | Copy-on-write fanout elimination | **0 qubits** at the binding op |
| GF(2) affine rank of the live state, 4,096 shots, two independent seeds | 1,218/1,234 (op 1.19M), 1,204/1,234 (op 4.42M), **1,233/1,234 (op 4.53M)** | CNOT-only (zero-Toffoli) compression | **≤1 qubit** at the binding op |
| Ops with ≥1,222 distinct live values | 183,556 ops in 4,549 ranges | Spike shaving | The peak is a long plateau, not a spike |
| Parked wires at the divide peak (idle ≥100k ops) | 170: 52 of input x, **118 ancillas in one block (~719–840)** | History compression | The leapfrog tape: the real width target |

The relations at ops 1.19M and 4.42M are real but sit off the binding op. They are parked *fanout copies*: seven copies of one bit on wires 239–245, four copies on 518/519/521/522 idle for ~600k ops, and 16 copies of wire 27 idle for 14k–25k ops. A copy-on-write pass would remove them for zero Toffolis. It would only move the maximum once the op-4.53M plateau has been lowered by something else.

**Conclusion.** The leader's width is information-dense. Linear (Clifford-only) compression is worth at most one qubit, so every remaining qubit has to come from a *non-linear* trade, which costs Toffolis. The largest parked block is the walk history, and the next probe is its decodability.
