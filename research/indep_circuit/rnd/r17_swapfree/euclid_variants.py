#!/usr/bin/env python3
"""R17: structural counts of Euclid formulations for a data-oblivious circuit (swap and realignment overhead).

Each variant runs the inversion of d mod p with cofactor tracking (u*d = +-f*... checked at the end) and reports:
  iterations      circuit iterations (each emits one digit for the current target)
  padding         iterations whose digit is forced to 0 (wasted work in a fixed schedule)
  swaps           data-dependent role changes (conditional swaps of rails and payload in a circuit)
  shift_max       largest relative realignment (bits) between consecutive iterations on the same target
  shift_events    iterations whose alignment differs from "previous minus 2" (need a conditional shift)
  tape_bits       fixed-length letter bits (digit + step-end flag) and shared_peak = max bits(f)+bits(g)+tape
  ok              d * u == +-1 (mod p) at the end
Variants:
  C0 classic Euclid, bit-serial (digits 0/1 per quotient bit), explicit swap at step ends
  C1 radix-4 nearest Euclid: signed digits in {-2..2} per base-4 position, remainder |r| < g, explicit swap
  C2 C1 with roles fixed by iteration parity (target A on even, B on odd): no swaps; the off-role iteration of a
     long quotient emits digit 0 (padding)
"""
import math
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from common import P, save, sweep  # noqa: E402


def bl(v):
    return abs(v).bit_length()


def radix4_digits(f, g):
    """Signed base-4 digits d_j in {-2..2}, most significant first, with f = sum d_j g 4^j + r, |r| < g (exact
    selection; a circuit selects from a top window). Returns (digits with their positions, r)."""
    k = max(0, (bl(f) - bl(g) + 1) // 2)
    r, digits = f, []
    for j in range(k, -1, -1):
        unit = g << (2 * j)
        dj = max(-2, min(2, round(r / unit)))
        r -= dj * unit
        digits.append((j, dj))
    while abs(r) >= g:              # final correction (rare with exact selection)
        dj = 1 if r > 0 else -1
        r -= dj * g
        digits.append((0, dj))
    return digits, r


def run_variant(d, variant):
    f, g = P, d
    uf, ug = 0, 1                   # cofactors: f = uf*d, g = ug*d (mod p)
    it = pad = swaps = shift_max = shift_ev = 0
    tape = 0.0
    peak = 0
    last_pos = None
    parity_role = 0                 # C2: which register the next iteration targets (0 = f-role, 1 = g-role)
    while g:
        if variant == "C0":
            q, r = divmod(f, g)
            nb = q.bit_length()
            for j in range(nb - 1, -1, -1):
                it += 1
                tape += 1
                if last_pos is not None and j != last_pos - 1:
                    shift_ev += 1
                    shift_max = max(shift_max, abs(j - (last_pos - 1)))
                last_pos = j
            tape += 1               # step-end flag
            uf, ug = ug, uf - q * ug
            f, g = g, r
            swaps += 1
        else:
            digits, r = radix4_digits(f, g)
            q_eff = (f - r) // g
            for j, dj in digits:
                if variant == "C2" and parity_role != 0:
                    it += 1         # off-role iteration: digit 0 on the other register
                    pad += 1
                    tape += math.log2(5)
                    parity_role ^= 1
                it += 1
                tape += math.log2(5)
                if last_pos is not None and j != last_pos - 1:
                    shift_ev += 1
                    shift_max = max(shift_max, abs(j - (last_pos - 1)))
                last_pos = j
                if variant == "C2":
                    parity_role ^= 1
            tape += 1 + 1           # step-end flag + remainder sign
            sign = -1 if r < 0 else 1
            uf, ug = ug, sign * (uf - q_eff * ug)
            f, g = g, abs(r)
            if variant == "C1":
                swaps += 1
            else:
                # C2: the roles alternate with the iteration parity; a step end is a swap only if the parity did not
                # already move the role to the new remainder's register
                if parity_role == 0:
                    swaps += 1
        peak = max(peak, bl(f) + bl(g) + tape)
    ok = (uf * d - f) % P == 0 and f in (1,)
    return {"iterations": it, "padding": pad, "swaps": swaps, "shift_max": shift_max, "shift_events": shift_ev,
            "tape_bits": round(tape, 2), "shared_peak": round(peak, 2), "ok": ok}


def c0(d):
    return run_variant(d, "C0")


def c1(d):
    return run_variant(d, "C1")


def c2(d):
    return run_variant(d, "C2")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out = {}
    for name, fn in (("C0_classic_bitserial", c0), ("C1_radix4_nearest", c1), ("C2_radix4_parity_roles", c2)):
        out[name] = sweep(fn, n, seed)
        a = out[name]
        print(f"{name:26s} ok {a['ok']}  iterations max {a['iterations']['max']} mean {a['iterations']['mean']}  "
              f"padding mean {a['padding']['mean']}  swaps mean {a['swaps']['mean']}  shift_events mean "
              f"{a['shift_events']['mean']} max_shift {a['shift_max']['max']}  shared_peak max {a['shared_peak']['max']}")
    print("saved", save(f"r17_variants_n{n}_s{seed}", out))
