# Can the point add run on one walk instead of two? (2026-10-26)

The leader runs two inversion walks per point add.
- **Divide.** A walk on dx = x2 − ox puts λ = dy/dx into y in place.
- **Multiply.** A walk on d′ = ox − x3 turns λ into y3 + oy = λ·d′ in place, which is also where λ is erased.

`validate.py` names the same value x2 − x3, with x2 the classical point. This is the leading lever toward the theoretical floor: one walk would cut roughly a quarter to a third of T.

## What one inversion can give: batch identities (checked)

[`research/one_walk/identities.py`](../research/one_walk/identities.py) checks these on secp256k1, 50/50 random point pairs:

    N = dx³ + 3·ox·dx² − dy²        d′ = N / dx²
    D = dx·N                        1/dx = N/D,   1/d′ = dx³/D

So **a single inversion of D** (Montgomery's batch trick) gives both inverses the point add needs. Computing (x3, y3) out of place therefore needs only one walk.

## Why that does not give an in-place point add with one walk

The obstruction is in-place cleanup, not the forward computation.
- A walk on D (forward traversal, payload, reverse traversal) needs D cheap to recompute at both traversals. The reverse traversal is what erases the transcript.
- 1/D is available only while the transcript is live.
- After the walk, every leftover register must be erasable with low-degree operations from what remains.

Every schedule tried leaves exactly one register that needs 1/d′ to erase:

| Register held when the transcript dies | D cheap there? | Erasing what is left |
|---|---|---|
| dx, x3′, y3′ (λ, dy, D already erased with 1/D) | yes, D = dx³·x3′ | dx = λ′² − x3 − 2ox with λ′ = (y3+oy)/d′: needs 1/d′ |
| u = 1/d′ (= dx³·D⁻¹), x3′, y3′ (dx erased with u) | yes, dx = g(u, x3′, y3′) | u itself is 1/d′: needs an inversion |
| outputs only | no: D = P³/d′⁵ in output coordinates | – |

**Valuation reason.** To give 1/dx, D must vanish where dx = 0. In output coordinates dx = P(x3′, y3′)/d′², so such a D has a pole at d′ = 0. A register that is regular on the input side and has a pole on the output side cannot be erased from the outputs without dividing by d′. A monomial D = dx^a·N^b is regular in both coordinate systems only for a = b = 0.

**Scope.** This is a statement about a construction class, not a lower bound.
- The class: one walk, low-degree polynomial operations otherwise, garbage erased by recomputation.
- Over F_p every function is a polynomial, so it proves nothing about all circuits.
- It does not cover: measurement-based erasure of λ followed by a phase fix (priced below); holding one transcript as a catalyst across both payloads (the table shows the last register still needs 1/d′); approximate tricks that spend λ budget.

**Literature.** Roetteler, Naehrig, Svore, Lauter 2017 (ePrint 2017/598, Remark 1): "the need for computing and uncomputing the slope λ leads to four calls to the inversion". Four inversion calls are two walks, each forward and reverse, which is what the leader does. Häner et al. 2020 (ePrint 2020/077) improve the inversion itself, not the count. No in-place one-inversion construction was found.

## Price of the alternative ways to clean up λ

The comparison is against the leader's multiply leg: a walk on d′ (rails forward and reverse) with one in-place payload pass.

| Route | What it needs | Against the leader's leg 2 |
|---|---|---|
| X-measure λ, phase (−1)^{m·λ} | λ = (y3+oy)/d′ recomputed for the phase: walk on d′, payload computed and uncomputed | ≥: the same walk, 2 payload passes instead of 1 |
| y3′ = λ·d′ out of place, then erase λ | erasing λ is a division by d′ | ≥: the same walk plus one n×n multiplication |
| Batch D, one walk on D | the last register needs 1/d′ (table above) | ≥: still a second walk on d′, plus the batch multiplications |

## Conclusion

Lever 1 is closed as a practical path. The leader already uses the known minimum of two walks. The gap between the 915M leader and the rough 400–500M floor sits in per-walk constants (T per halving step, the transcript's width), not in the walk count.
