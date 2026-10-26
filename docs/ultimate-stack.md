# From DivPay to the best combination, one technique at a time (2026-10-26)

Script: [`research/novel/stack.py`](../research/novel/stack.py). Sources per step:
- **M**: this repo's model or measurement (the jump tick count is from `jump_divsteps.py`).
- **C**: community-measured effect in the same GCD family (submission notes).
- **L**: the leader's measured phase costs.

| Step | T | Q | Score | Δ | Source |
|---|---|---|---|---|---|
| S0 DivPay T6 (divsteps, exact) | 2.16M | 1,418 | 3.06B | | M |
| S1 + multi-bit shift, one fold per tick (G28, G25) | 1.94M | 1,519 | 2.95B | −3.9% | M: 317 ticks instead of 535 steps; tape 951 bits instead of 850 |
| S2 + conditional replay (G26) | 1.87M | 1,519 | 2.84B | −3.5% | C |
| S3 + Karatsuba square (G22) | 1.86M | 1,519 | 2.83B | −0.4% | C |
| S4 + interleaving and hosting (G30, G04) | 1.86M | 1,499 | 2.79B | −1.3% | C |
| S5 + ping-pong, leapfrog, lever A (G29, G34–G36) | 0.78M | 1,243 | 0.975B | −65% | L, plus +43k T for exactness |
| S6 + conditionally clean ancillae (unused) | 0.78M | 1,240 | 0.973B | −0.2% | M, estimate |
| S7 + radix packing of the tape (unused) | | | | 0 | M: the tape is already at its local floor |
| S8 + pebbling / spooky pebbling (unused) | | | | 0 | M: the trade is flat |

## Findings

**The leader's walk is the decisive technique.** Ping-pong and leapfrog together (S5) are worth 65%. Everything else is a few percent.

**After S5 the stack is the leader's architecture.** What DivPay contributes there is only exactness by design, and that is more expensive than making the leader exact (+43k T).

**Best combination: ≈0.97B, exact and without grinding.** That is ~6% above the leader's 0.915B, which needs λ ≈ 16 plus a nonce grind. None of the unused techniques adds more than a few qubits. No path "far below the leader" was found; the measured local floors (transcript, payload adds, two walks) explain why.

**Under 1,050 qubits and under 3B is feasible, but costs score.** The community's measured points:

| Point | Q | T | Score |
|---|---|---|---|
| 1,152-qubit route (39e28ee) | 1,152 | 1.32M | 1.52B |
| Theta | 893 | 2.22M | 1.98B |

Interpolating gives ~1.67M T at 1,050 Q, about **1.76B**. That beats Google (2.99B and 3.17B) and is ~1.9× the leader.
