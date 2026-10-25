# Provenance and asymmetric dataflow

The new architecture frontend in this repository is written independently of the upstream circuit implementation. It uses established field identities, GF(2) elimination, and measurement-based uncomputation. It is a research prototype, not a claim that these principles are new or absent from other submissions.

The full-circuit target remains **Q ≤ 1,080 and average executed Toffolis ≤ 850,000**, with Q ≤ 1,050 as a stretch width. No complete circuit at that target has been produced.

## Architecture invariants

1. **Respect the benchmark interface.** The field DAG starts from affine `(px, py)` and classical `(qx, qy)` and ends at affine `(rx, ry)`. Its current generic formula requires `dx != 0`; doubling, inverse-point, and infinity handling remain explicit obligations. A Jacobian implementation needs a complete conversion and cleanup proof before comparison.
2. **Keep data and classical control distinct.** Field values are quantum data; measurement outcomes are classical controls. Asymmetric schedules may have different lifetimes, but a classical clock domain does not remove a causal dependency or permit reading an unknown field value as classical data.
3. **Give scratch an owner.** Each `RegionCompiler` has a fixed scratch budget. Leases cannot cross stages, overlap on a live wire, or survive a generation change. The report exposes both reserved width and peak active width. Fixed disjoint pools may increase the whole-circuit footprint; no global improvement is assumed.
4. **Repair phase before reuse.** Each lease records the defining Boolean function and the versions of its data controls. Recycling checks those versions, emits X-basis measurement and the exact conditional phase repair, and only then releases the wire. An overwritten control blocks recycling.
5. **Retain algebraic provenance.** Every emitted CNOT, CCX, measurement, and correction records a field-node identifier and a bit-level expansion. This is traceability, not an automatic proof that a user-supplied expansion implements an entire field operation. The complete modular multiplication and inversion backend remains unwritten.
6. **Delete only certified work.** Field expressions unreachable from declared outputs can be removed before gate emission. Once an expression has produced quantum scratch, it also has a cleanup obligation. Magnitude bounds or a small sampled value do not justify pruning a live coordinate or carry.

## Sparse bilinear lowering

For separate bit vectors `a` and `b`, a bilinear scratch function has the form

`f(a,b) = aᵀ M b` over GF(2).

The compiler decomposes the binary matrix as `M = XOR_k u_k v_kᵀ`. To compute each term, it builds the two parities on existing operand wires using reversible CNOT conjugation, applies one CCX into the scratch target, and restores the operand basis. No extra parity qubit is allocated. The number of CCX gates is the number of rank-one factors, rather than the number of nonzero matrix entries in the direct partial-product expansion.

The elimination is exact: choose a nonzero pivot row `v`, select the rows `u` whose pivot-column bit is one, and XOR `u vᵀ` from the remaining matrix. This clears that row and column. Repeating gives an exact reconstruction. The original monomials remain in the cleanup certificate alongside the factorization.

After a useful coherent reader has consumed `f`, X-basis measurement of scratch gives outcome `m` and phase `(-1)^(m f(a,b))`. The compiler applies CZ to each pair of parities under `m`, restoring each parity basis afterward. This cancels the phase with zero CCX cleanup. The source operands must remain available. Quadratic repairs include **CZ**, so a simple frame of single-qubit X/Z corrections is insufficient in general.

This is a partial-product transformation. Integer carries and reduction modulo the secp256k1 prime remain nonlinear work. The matrix rank does not supply a Toffoli estimate for a complete GF(p) multiplier or GCD inversion.

## Recorded demonstration

The example computes two successive bilinear parity expressions, XORs each into a coherent accumulator, and recycles the same scratch wire. It does not erase an unused computation and call that a saving.

| Quantity | Direct partial products | Rank-factored, coherent cleanup | Rank-factored, measured cleanup |
| --- | ---: | ---: | ---: |
| Compute CCX | 5 | 2 | 2 |
| Cleanup CCX | 5 | 2 | 0 |
| Total CCX in the two scratch routines | 10 | 4 | 2 |

The measured variant has **six active/reserved qubits**, two X-basis measurements, two classical outcome bits in total, and six classically conditioned correction gates (four CNOTs and two CZs). Its emitted wire ordering has Toffoli depth two and two measurement rounds. These dependency counts have no physical routing or cycle-time assumption. Conditional branches are accounted for in the emitted record. Measurement/readout latency and classical distribution latency depend on the hardware and are not assigned fabricated constants.

At two logical Toffolis, illustrative decompositions use eight T magic states in a measurement-assisted 4T scenario or fourteen in an exact unitary 7T scenario. These are declared assumptions, not physical resource estimates: decomposition ancillas, factory space, distillation levels, QEC cycles, routing, and physical failure rates are not included. [The exported record](../data/provenance-demo.json) leaves unavailable physical estimates unset.

## Verification and remaining work

`python3 -m unittest discover -s tests -v` checks the field frontend over every generic point pair on a small nonsingular curve, rejects undefined inversion, verifies dependency-based pruning, and exercises ownership, stale leases, and control-version rejection.

`python3 -m architecture.verify` checks the actual emitted gates on coherent inputs for every 2×3 binary matrix, every measurement branch, and sequential scratch reuse. All 132 branches pass; exhaustive reconstruction also covers every 3×3 binary matrix. [Recorded result](../data/bilinear-check.json). The independent quadratic-cleanup checks cover another 512 measurement branches.

The next integration gate is an actual 256-bit arithmetic lowering that preserves these origin and cleanup records. It must then demonstrate a saving after the upstream circuit's existing passes, pass the untouched challenge evaluator, and report independent-input failures. Component checks do not establish the 850,000-Toffoli target or universal point-addition correctness.
