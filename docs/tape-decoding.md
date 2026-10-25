# Can the leapfrog tape be decoded instead of stored?

Question (candidate 1 from the [width audit](width-audit.md)): andigu/uncompute ([arXiv:2610.22367](https://github.com/andigu/uncompute/tree/main/tasks/modinv-point-add/circuits/divsteps)) avoids storing most *divstep* branch decisions by recovering them from parity, sign and the surviving arithmetic state. Does the same work for the leader's *leapfrog* walk?

## Evidence that the parked block is the tape

At the divide peak (op 1,190,586), the 118 ancillas parked for ≥100k ops were created in small groups (gaps of 3–17 ops inside a group, ~3k–14k ops between groups) between ops 77k and 585k, one group per walk tick. They are cleared during the reverse walk, ops 1.19M–4.39M: 83 by HMR and 35 by CX.

## Test

[`research/leapfrog_decode.py`](../research/leapfrog_decode.py) re-implements one tick exactly as the `leapfrog.rs` header specifies: three forced add-halve steps with s = +1 iff T ≡ B (mod 4), then a deep/flat fourth step with an e-fold barrel strip. It runs random walks d ∈ [1, p), and for each step asks whether the post-step state (T′, B) determines the letter.

| Decoder | Forced steps (s) | Fourth step (s, e) |
|---|---:|---:|
| Smallest-magnitude predecessor | 65.1% correct | 26.1% correct |
| Width envelope: only one candidate predecessor fits the tick's empirical rail width | **0.6% unique**, 99.3% ambiguous | **0.0% unique**, 100% ambiguous |

Letter statistics (2,000 walks): forced s is uniform (H = 1.000 bit); the fourth step has H = 2.751 bits. That is **5.75 bits per tick**, 112.8 ticks on average (max 122), about **649 bits of branch information per walk**.

## Why the trick does not transfer

Parity cannot decode a forced step: both predecessors 2T′ ∓ B are odd and satisfy the selection rule. Magnitude cannot either: the two candidates differ by 2B, and B is as wide as the envelope. Divsteps are decodable because the δ counter and the sign of g constrain which branch was legal. Leapfrog removed that structure (a fixed alternating schedule and no counter) to make the forward step Clifford-cheap. Its letters therefore carry a full ~5.75 bits of fresh entropy each.

There is an information bound in the other direction. The whole tape is a function of d, so its *joint* entropy is at most 256 bits, against 649 bits of marginal letter entropy. The leader's ~100-qubit tape growth means it already stores far less than the raw 6 bits per tick. That fits this bound: the remaining branch information sits in the rails.

**Verdict:** algebraic branch decoding **does not apply** to the leapfrog walk. It is available only by switching to a decodable walk (divsteps with a counter), and andigu's own figures (≈4.0M T at 935 Q) price that route at far more than the ≈687 T per qubit a record needs. Candidate 1 is closed.

## Payload redundancy (candidate 2), also closed

P_i = λ·R_i makes the two 256-qubit payload registers jointly redundant given λ and the rails, but the relation is *multiplicative*. Rebuilding P_B from P_T on a tick needs a modular multiply or divide, which costs orders of magnitude more than ≈687 T per qubit. The only cheap instance is the park tie (P_T = ±P_S once R = (±1, ±1)), and the leader already exploits it (`leapfrog.rs:4041`). The cheap arithmetic-relation case (block = ±block + c, about 1–2 T per qubit) is additive and does not cover this.
