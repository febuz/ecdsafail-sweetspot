#!/usr/bin/env python3
"""Cost model of the novel point add ("DivPay"), built without the leader's constructs.

Allowed: generic primitives (Toffoli/AND, Gidney adder n-1 T with n ancillas, CDKM ripple adder 2n T with 1 ancilla,
Fredkin = 1 T, controlled constant add n T, measurement-based AND uncompute) and the unused techniques below.
Excluded leader constructs: leapfrog walk, lever-A rails/record, fitted width tables/anchors, IPK fold tables,
tape-replay payload P = lambda*R, Karatsuba square, merged Montgomery op, post-pass rewriters, nonce grinding.

Structure (Roetteler-style, in place): dx, dy -> y <- dy/dx (walk 1) -> x <- x + 3ox - y^2 -> y <- y*d' (walk 2) -> final subs.
Inversion: half-delta divsteps, 591 fixed steps (exact, proven bound), rails widths from divsteps_sim.py.
"""
import random

from divsteps_sim import P, STEPS, run

N = 256


def envelope(samples=1500, margin=2):
    """Per-step max rail width over samples (+margin), and letter statistics."""
    rnd = random.Random(11)
    mx = [0] * STEPS
    for _ in range(samples):
        _, _, w, _ = run(rnd.randrange(1, P))
        for i, (a, b) in enumerate(w):
            mx[i] = max(mx[i], a, b)
    return [m + margin for m in mx]


def walk_cost(env, payload, pad, transcript_bits_per_step, rails_adder="gidney"):
    rails_step = [2 * w for w in env]                     # controlled swap (w Fredkin) + controlled add-sub (w)
    delta_logic = 30                                       # 10-bit delta: sign test, controlled negate, increment
    rails_pass = sum(rails_step) + delta_logic * STEPS
    if rails_adder == "cdkm":
        rails_pass += sum(env)                             # ripple adder costs 2n instead of n
    if payload == "modp":                                  # (u, v) mod p, comparison-based modular add
        pay = STEPS * (N + 3 * N + N)                      # swap + modular add-sub (~3n) + modular halve (n)
        extra = 0
    elif payload == "coset":                               # coset representation (Zalka/Gidney): no compares
        pay = STEPS * 3 * (N + pad)                        # swap + plain add-sub + controlled +p then shift
        extra = 0
    elif payload == "integer":                             # integer cofactors grow ~N/STEPS bits per step
        pay = sum(3 * max(8, int(N * i / STEPS)) for i in range(STEPS))
        extra = 2 * (N * N // 2 + 2 * 33 * N)              # y*u mod p and the erase of y via d (schoolbook, Solinas)
    t = 2 * rails_pass + pay + extra                       # rails forward + reverse, one payload pass
    return t


def peak_q(env, payload, pad, transcript_bits_per_step, rails_adder="gidney"):
    tape = transcript_bits_per_step * STEPS
    pay = 2 * (N + (pad if payload == "coset" else 0))
    rails_end = 2 * env[-1]
    if payload == "integer":
        pay = N + N                                        # y + product register
        rails_end = 2 * N + 8                              # rails + one cofactor column share ~2N bits (|f||v| ~ p)
    anc = N + pad if rails_adder == "gidney" else 2
    return tape + pay + anc + rails_end + 12 + 40          # + delta register + misc ancillas


def main():
    env = envelope()
    square = N * N // 2 + 2 * 33 * N + 2 * N               # schoolbook square + Solinas reduction + subtract
    coords = 4 * N
    leader = 741_719 * 1_234
    print(f"rail envelope: sum {sum(env)} bits over {STEPS} steps (start {env[0]}, step 300 {env[300]})")
    print("variant                                     T        Q     score   vs leader")
    for name, pay, pad, tb, ra in [
        ("A  mod-p payload, 2-bit letters", "modp", 0, 2, "gidney"),
        ("B  coset payload, 2-bit letters", "coset", 24, 2, "gidney"),
        ("C  coset payload, trit-packed letters", "coset", 24, 5 / 3, "gidney"),
        ("D  integer cofactors, trit letters", "integer", 0, 5 / 3, "gidney"),
        ("E  D + CDKM rails (ancilla-free)", "integer", 0, 5 / 3, "cdkm"),
    ]:
        t = 2 * walk_cost(env, pay, pad, tb, ra) + square + coords
        q = peak_q(env, pay, pad, tb, ra)
        print(f"{name:40s} {t / 1e6:6.2f}M {q:6.0f} {t * q / 1e9:6.2f}B  {t * q / leader:5.2f}x")


if __name__ == "__main__":
    main()
