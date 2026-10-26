#!/usr/bin/env python3
"""Novel point add from textbook primitives only (no leader constructs), costed bottom-up.

Primitives (Toffoli count, live ancillas), n = register width:
  CNOT/CZ/SWAP/X                         0 T                    (2-qubit, Clifford)
  Toffoli / CCZ / Fredkin / Peres         1 T                    (3-qubit)
  temporary AND (Jones 2013, Gidney 2018) 1 T, uncompute by X-measurement = 0 T
  Gidney ripple adder                     n-1 T, n ancillas
  chunked ripple adder (block size k)     n-1 + 2*ceil(n/k) T, k+1 ancillas  (carry saved/restored per block; estimate)
  CDKM (Cuccaro) adder                    2n-1 T, 1 ancilla
  sign-controlled add/subtract            same as the adder (sign XORed into the operand)
  controlled constant add (+-p)           n T
  controlled swap of n wires (Fredkins)   n T
  top-window comparator (w bits)          w T  (exact except within 2^(n-w) of the threshold)
  schoolbook square + Solinas fold        n^2/2 + 9*2n T
Inversion: half-delta divsteps truncated at N steps (tail measured by steps_tail.py), rails envelope from divsteps_sim.
Payload (u, v) mod p per step: swap, add/sub, mod-p correction (2 window compares, one +-p add, flag erase by 2 compares),
halving (controlled +p, shift, parity flag erased by a window compare). Letters: ternary (even / odd / odd+swap), packed
5 trits in 8 bits.
"""
import math
import random

from divsteps_sim import P, run

N_BITS = 256
LEADER = 741_719 * 1_234
GOOGLE = {"Google low-qubit (2.7M x 1175)": 2_700_000 * 1_175, "Google low-gate (2.1M x 1425)": 2_100_000 * 1_425}


def envelope(steps, samples=1500, margin=6):  # 6: 200k-input envelope exceeds the 1,500-sample one by up to 8 bits on single steps; sum matches 200k + 2
    rnd = random.Random(11)
    mx = [0] * 591
    for _ in range(samples):
        _, _, w, _ = run(rnd.randrange(1, P))
        for i, (a, b) in enumerate(w):
            mx[i] = max(mx[i], a, b)
    return [m + margin for m in mx[:steps]]


def adder(n, kind, k):
    if kind == "gidney":
        return n - 1, n
    if kind == "chunk":
        return n - 1 + 2 * math.ceil(n / k), k + 1
    return 2 * n - 1, 1  # cdkm


def design(steps, env, kind="gidney", k=32, win=40, pad_letters=8 / 5, cmp_anc=None):
    n = N_BITS
    add_t, add_q = adder(n, kind, k)
    # rails pass: per step controlled swap (w Fredkins) + sign-controlled add/sub (w) + delta logic + letter pack
    rails = sum(w + adder(w, kind, k)[0] for w in env) + steps * (30 + 12)
    # payload pass per step
    swap = n
    addsub = add_t
    modfix = 2 * win + add_t + 2 * win    # the +-p constant add pays the same adder cost as the others
    halve = add_t + win
    pay = steps * (swap + addsub + modfix + halve)
    walk = 2 * rails + pay
    square = n * n // 2 + 9 * 2 * n + add_t
    coords = 4 * n
    t = 2 * walk + square + coords
    tape = math.ceil(steps * pad_letters)
    q = tape + 2 * n + 2 * env[-1] + 11 + add_q + (win if cmp_anc is None else cmp_anc) + 8
    return t, q, dict(rails=rails, pay=pay, tape=tape, adder_q=add_q)


def main():
    print("variant                                         T        Q    score   vs leader  vs Google low-gate")
    rows = [
        ("T1 proven 591 steps, Gidney adders", 591, "gidney", 32),
        ("T2 545 steps (tail 5e-9/inv), Gidney", 545, "gidney", 32),
        ("T3 545 steps, CDKM adders", 545, "cdkm", 32),
        ("T4 545 steps, chunked adder k=32", 545, "chunk", 32),
        ("T5 540 steps, chunked adder k=16", 540, "chunk", 16),
        ("T6 535 steps, k=16, 27b/17 trits, KG comparator", 535, "chunk", 16),
    ]
    envs = {}
    for name, steps, kind, k in rows:
        env = envs.setdefault(steps, envelope(steps))
        extra = dict(pad_letters=27 / 17, cmp_anc=4) if name.startswith("T6") else {}
        t, q, parts = design(steps, env, kind, k, **extra)
        s = t * q
        print(f"{name:45s} {t / 1e6:5.2f}M {q:6d} {s / 1e9:6.2f}B  {s / LEADER:6.2f}x   {s / GOOGLE['Google low-gate (2.1M x 1425)']:6.3f}x"
              f"   [rails {parts['rails'] / 1e3:.0f}k/pass, payload {parts['pay'] / 1e3:.0f}k/walk, tape {parts['tape']}]")
    for g, v in GOOGLE.items():
        print(f"{g:45s} {v / 1e9:.2f}B")


if __name__ == "__main__":
    main()


def strict(steps, env):
    """None of the leader's constructs from the Gebruikt catalog (G-ids); elementary gates, adders and comparators are
    shared by every circuit and stay allowed. Concretely: no measurement-based uncompute (adders 2n-1 with
    Toffoli uncompute, 1 ancilla: CDKM), full-width comparators (n), no Solinas fold (generic Montgomery reduction of
    the square, ~n^2), no window truncation. Trimming the step count is itself 'partial' in the leader (round trimming),
    so the proven 591 is the strict choice."""
    n = N_BITS
    add_t = 2 * n - 1
    rails = sum(w + (2 * w - 1) for w in env) + steps * (30 + 12)
    pay = steps * (n + add_t + (4 * n + add_t) + (add_t + n))   # constant adds as CDKM (2n-1), full compares n
    walk = 2 * rails + pay
    square = n * n // 2 + n * n + add_t
    t = 2 * walk + square + 4 * n
    tape = math.ceil(steps * 27 / 17)
    q = tape + 2 * n + 2 * env[-1] + 11 + 1 + 4 + 8
    return t, q


if __name__ == "__main__":
    for steps in (591, 535):
        env = envelope(steps)
        t, q = strict(steps, env)
        s = t * q
        print(f"STRICT {steps} steps: T {t / 1e6:.2f}M  Q {q}  score {s / 1e9:.2f}B  vs Google low-gate {s / 2_992_500_000:.2f}x  vs leader {s / LEADER:.2f}x")
