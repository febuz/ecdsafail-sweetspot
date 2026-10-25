# TRSR: a benchmark-safe interpretation

**Research proposal, not a validated circuit.** TRSR denotes teleport-routed, sparse, recycled arithmetic. Its three components have different effects on the ECDSA.fail score and must be priced separately.

## 1. Sparse linear arithmetic

For a genuinely linear Boolean map `y = A x` over GF(2), each `1` in a sparse matrix `A` can become a CNOT in a direct implementation. Synthesis can reduce the CNOT count further by sharing parity subexpressions. This can improve physical routing and Clifford depth while charging zero Toffolis in the benchmark.

secp256k1's prime is `p = 2^256 − 2^32 − 977`. Its sparse constant makes shifts and parts of the Solinas reduction cheap. **Modular addition, multiplication, and inversion are not linear GF(2) maps:** carries and variable products remain nonlinear and require charged gates. Existing leaderboard circuits already exploit sparse constants and measured carries. A TRSR claim must isolate a new gate saving beyond those constructions, with the generated op stream and evaluator as evidence.

## 2. Recycle scratch without dephasing the data

Let live qubits `a,b` control a clean scratch qubit `c`, prepared as `c = a ∧ b`. When `c` has no remaining readers, measuring `c` in the **X basis** produces an outcome `m` and a phase `(-1)^(mab)` on the live data. A classically conditioned `CZ(a,b)` removes that phase. The scratch can then be reset and reused. This replaces the coherent Toffoli uncompute with an X-basis measurement plus Clifford correction, assuming `a` and `b` still hold the right values. The challenge already supports this pattern through `HMR` and classically conditioned phase gates; the opportunity is to find additional safe live ranges.

For a linear scratch word `c = A x`, X-basis measurement outcomes form a vector `m`. Applying `Z` to the live input bits indicated by `Aᵀm` corrects the phase `(-1)^(m·Ax)`. Sparse `A` makes this correction sparse. This is a **zero-Toffoli cleanup only when the relevant input state remains available** and the scratch has not acquired other dependencies.

Measuring arbitrary garbage in the Z basis and resetting it is invalid. For example, measuring one half of `(|00⟩ + |11⟩)/√2` in Z reveals and dephases the other half. A Pauli-frame update cannot generally restore that coherence. A candidate must prove its measurement identity, ancilla cleanup, relative phase, and forward–reverse behavior.

## 3. Teleportation for physical routing

Bell-pair teleportation can route a logical state across distant fault-tolerant modules with measurement and classical feedforward. It may lower physical SWAP depth on a layout with expensive communication. The Bell-pair qubits, creation, distillation, error-correction cycles, feedforward latency, and routing success all have a cost. The ECDSA.fail harness has no geometric routing model and does not score SWAP depth or energy; a teleportation change alone cannot establish a lower `Q × T` score. Physical-module communication should be evaluated after a valid logical circuit is found.

## Candidate execution schedule

1. Partition each arithmetic stage into live data, reusable scratch, and retained reversible history. Record first and last reads at every peak.
2. Synthesize sparse linear maps and phase corrections as CNOT/Z/CZ networks, keeping nonlinear carry and product counts explicit.
3. Select scratch whose defining Boolean function is still computable from live registers. Apply X-basis measured uncompute and exact conditional phase repair; recycle only after correction.
4. Checkpoint or recompute long-lived history and payloads where the Toffoli cost is below the available 108,281-gate budget for reducing the leader's width by 154 qubits.
5. Measure `Q`, average executed `T`, Toffoli depth, Clifford count, measurement count, and a physical-routing estimate separately. Run the official evaluator before claiming a result.

The benchmark's task is one coherent secp256k1 point addition with a classical addend, so a complete Shor resource claim needs additional windowing and full-algorithm accounting. See the [ECDSA.fail paper](https://arxiv.org/abs/2609.09582).
