# Is there a field inversion that is neither Fermat nor a GCD walk, within 1.5× the leader?

Budget: the leader spends ≈742k average executed Toffolis on two field divisions plus the square, about ≈350k per division (47% / 48% of T). "At most 1.5×" therefore means **≤ ≈525k Toffolis per inversion**.

## Theorem (algebraic methods need ≥ 256 multiplications)

Let a straight-line program over F_p use +, −, × and constants, with k multiplications or squarings, and compute x ↦ x⁻¹ for x ≠ 0 (with 0 ↦ 0). Then **k ≥ ⌈log₂(p − 2)⌉ = 256** for secp256k1.

*Proof.* The program computes a polynomial g ∈ F_p[x] with deg g ≤ 2^k: each multiplication at most doubles the degree, and additions do not raise it. As functions on F_p, g = x^{p−2}. Two polynomials define the same function on F_p iff they agree modulo x^p − x. x^{p−2} is reduced (degree < p), and reduction modulo x^p − x never raises degree, so deg g ≥ p − 2. Hence 2^k ≥ p − 2. ∎

This covers Fermat (x^{p−2}), every addition chain, and any "inversion-free" algebraic trick. Fermat for secp256k1 reaches the bound almost exactly: 255 squarings + ~15 multiplications.

**Consequence.** To stay within 525k Toffolis, a 256-bit modular squaring would have to cost **≤ 525,000 / 256 ≈ 2,050 Toffolis**. Schoolbook needs ≈ n² = 65,536 (≈30% less with [Litinski 2024](https://arxiv.org/abs/2410.00899)). Even bare Karatsuba recursion to 1-bit leaves has 3⁸ = 6,561 AND products before counting a single carry ([Gidney 2019](https://arxiv.org/abs/1904.07356)). Squaring x ↦ x² is 2-to-1 on F_p*, so a reversible chain must also keep or recompute intermediates (Bennett), which adds cost on top. **The entire algebraic family is at least ~10× and realistically 20–50× over budget.** This is a proof for the operation count, combined with the best known multiplier costs.

## Other non-walk ideas, checked

| Idea | Verdict | Why |
|---|---|---|
| Projective / Jacobian coordinates (no division inside the formulas) | **Does not avoid it.** | The challenge has affine input and output. In Shor, a unique projective representation without division is an open problem; known conversions cost 2C + 2D, with D a division ([Häner et al. 2020](https://arxiv.org/abs/2001.09580), [arXiv:2502.12441](https://arxiv.org/abs/2502.12441), [ePrint 2026/106](https://eprint.iacr.org/2026/106)). |
| Montgomery batch inversion (one inversion for many) | Not applicable | The two divisions in one addition are sequentially dependent (λ, then uncomputing λ). |
| Itoh–Tsujii / Frobenius tricks | Not applicable | Only for extension and binary fields; secp256k1 is a prime field. |
| Table lookup (QROM) of inverses | Impossible | 2²⁵⁶ entries; inversion has no small-window decomposition. |
| Subquadratic half-GCD / jumpdivsteps | No reversible construction found | At n = 256 the multiplication-based recursion is past no crossover, and it is itself Euclid-type. |

## Conclusion

Field inversion in F_p comes in two families: algebraic (≥ 256 multiplications, provably far over budget) or bit-level Euclid-type ("walks"). **There is no third family within 1.5×.** The candidates under budget are all walks:

| Walk | Exact? | Expected cost vs leader |
|---|---|---|
| Leapfrog (leader) made exact | target | ≈1.0× + the price of exactness: the divide failures are a one-bit width-envelope shortfall, so a proved width table is needed |
| Bernstein–Yang hddivsteps, fixed 591 steps (proved bound, [sipa](https://github.com/sipa/safegcd-bounds)) | **proved** | ≈1.4× Toffoli (cost model), but ≈1,182 extra history qubits unless decoded; see [exactness experiments](exactness-experiments.md) |
| andigu divsteps with decoding ([arXiv:2610.22367](https://arxiv.org/abs/2610.22367)) | sampled | ≈5× (4.0M T at 935 Q) |
| Register-sharing EEA with a proved bound ([arXiv:2607.13816](https://arxiv.org/abs/2607.13816)) | proved | ≈90× |
