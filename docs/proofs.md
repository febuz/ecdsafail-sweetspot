# What is proved, what is measured

Every claim in this repository falls into one of three classes:
- **Proved:** holds for all inputs, by a complete argument or a decision procedure.
- **Measured:** an exact, reproducible count on a fixed artefact.
- **Empirical:** holds on sampled inputs only.

## The proof tool

[`architecture/anf_prover.py`](../architecture/anf_prover.py) decides equivalence for circuits over {X, CX, CCX, SWAP, Z, CZ, CCZ, NEG}.

**Theorem 1 (completeness).** Such a circuit acts as U|x⟩ = (−1)^φ(x) |F(x)⟩. U₁ = U₂ iff F₁ = F₂ and φ₁ = φ₂ as Boolean functions. The algebraic normal form over GF(2) is unique, so equal ANFs prove equality on all 2ⁿ inputs. A non-zero ANF difference yields a counterexample: set exactly the variables of a minimum-degree monomial to 1. Only that monomial survives evaluation.

**Corollary (label independence).** Wires are free variables. An identity proved for one labelling therefore holds for every instantiation with pairwise distinct wires.

The prover agrees with brute force on 300 random 4-qubit circuits ([`tests/test_anf_prover.py`](../tests/test_anf_prover.py)).

## Our improvements

| Claim | Class | Basis |
|---|---|---|
| `inverse_pair`, `shared_control_factor`, `shared_product_fanout`, `phase_conjugation` ([`rewrites.py`](../architecture/rewrites.py)) | **Proved** | Theorem 1 |
| Two-bit GF(2) polynomial Karatsuba: 4 → 3 Toffolis | **Proved** | Theorem 1 |
| CCX(a,b,t)·CZ(t,x)·CCX(a,b,t) = CZ(t,x)·CCZ(a,b,x): 2 → 1 Toffoli-class gate | **Proved** | Theorem 1 |
| X-basis cleanup of a scratch holding f(x), repaired by (−1)^{m·f(x)} ([`sparse_recycle.py`](../circuits/sparse_recycle.py)) | **Proved** | HMR leaves phase (−1)^{m·f}; repair applies (−1)^{m·f} again, and the product is the identity on every branch m ∈ {0, 1}. Also checked on 512 branches. |
| Quadratic ANF → parity products ([`quadratic.py`](../architecture/quadratic.py)) | **Proved for n ≤ 4**, algorithm general | Exhaustive reconstruction of all 2,048 quadratic ANFs on 4 inputs. The general case is symplectic elimination of an alternating GF(2) form. |
| None of these rules fires on the leader's 10.2M-op stream | **Measured** | [`stream_rule_screen.py`](../analysis/stream_rule_screen.py) |

## Negative results

| Claim | Class |
|---|---|
| Leapfrog forced steps cannot be decoded from parity | **Proved.** Both predecessors 2T′ ∓ B are odd and satisfy s = +1 ⇔ T ≡ B (mod 4). |
| Leapfrog letters are ambiguous under the width envelope (99.3–100%) | Empirical (2,000 walks) |
| Leader width: renaming slack 0; copy slack 0 at the binding op; affine rank 1,233/1,234 there | **Measured** (GF(2) rank on 4,096 shots can only overstate dependencies) |
| The leader passes only on its own shot set | **Measured.** Deterministic re-runs of `eval_circuit`: 0 mismatches as built, 18–19 after a no-op `X;X` reseed. |

## The leader's stream-bound cuts (`lane3_sigcut`, 830 edits)

[`analysis/prove_cuts.py`](../analysis/prove_cuts.py) runs a sound bounded-ANF dataflow over opaque atoms (cap 64 monomials) on the stream *before* the cuts. That stream comes from a rebuild with the post-edits disabled ("variant E"). A cut is proved when its side condition holds on terms.

| Cut type | Count | Proved | Unproved |
|---|---:|---:|---:|
| HMR → park (SWAP into a clean wire) | 373 | **359** | 14 |
| CCX → unpark SWAP (reuse a parked product) | 372 | **8** | 364 |
| CCX → CX (reuse an existing copy) | 60 | **1** | 59 |
| CCX → delete (product is zero) | 25 | **7** | 18 |
| **Total** | 830 | **375** | 455 |

The unproved unparks reuse a product parked ~500k ops earlier in the forward walk. Their equality rests on the reverse walk restoring the forward state, a *walk-level* reversibility invariant that local algebra cannot express (adder terms exceed any ANF bound). Empirically, the leader (with all post-edits) and variant E (without them) fail on **exactly the same 8 of 4,096 fresh inputs**. All post-edits together save **1,334 executed Toffolis** (743,140 → 741,805) and introduce no new failures on those inputs.

**Correction to [shot-set dependence](shot-set-dependence.md):** the ≈19 expected failures do *not* come from the post-edits. Failure localization ([`research/localize_failures.py`](../research/localize_failures.py), 32 failing shots over 4 seeds) puts 44% in the divide walk, 0% in the square and 56% in the multiply walk, i.e. in the core walk generation.
