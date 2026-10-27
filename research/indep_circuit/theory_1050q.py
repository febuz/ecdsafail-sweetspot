#!/usr/bin/env python3
"""Speculative qubit levers on top of the ~850k-T paper design (theory_850k.py, row 9: 848,591 T, 1,671 Q).

Peak of row 9 (end of the forward walk): tape 813 + payload pair 560 (2 x (256 + pad 24)) + carries 258 + misc 40.
Status: T = textbook, S = speculative, S! = needs a new result. All numbers are paper estimates.
"""
n = 256
T, tape, pay, carries, misc = 848_591, 813, 560, 258, 40
rows = [("9 (from theory_850k.py)", T, tape + pay + carries + misc, "")]

# Q1 (T): chunked carries (blocks of 32 + one saved carry per block) in all late-walk adds; +T from theory_850k row 8
T += 56_933
carries = 40
rows.append(("Q1 chunked carries, k = 32 (T)", T, tape + pay + carries + misc, "carries 258 -> 40"))

# Q2 (S): payload padding 24 -> 6 bits; needs a range proof for the deferred correction with fewer guard bits
pay = 2 * (n + 6)
rows.append(("Q2 payload guard bits 24 -> 6 (S)", T, tape + pay + carries + misc, "range proof for deferred correction"))

# Q3 (S): block arithmetic coding of the jump-tick letters over 8-tick blocks, ~2.3 bits/tick instead of 2.67
tape_new = round(305 * 2.3)
T += 2 * 2 * 305 * 30                                  # encode + decode per tick, both legs
tape = tape_new
rows.append(("Q3 block arithmetic coding of letters (S)", T, tape + pay + carries + misc, "letter entropy <= 2.3 b/tick to be measured"))

# Q4 (S): transposed integer-cofactor payload. No payload during the forward walk; during the reverse rails pass the
# row vector e1^T M_S ... M_1 is built in reverse step order as integers (it grows while the tape is consumed).
# Walk peak: tape + y + rails end + carries + misc.  End: m11 erased by exact 2-adic division (m11 = (2^K - m12 d)/p),
# then y <- y * m12 * 2^-K (mod p) as an in-place multiplication: z = y*u out of place, y erased with z * d * 2^-K.
walk_peak = tape + n + 20 + carries + misc
pay_ticks = 305 * 2 * 140                               # integer row update ~2 x mean cofactor width per tick
pay_old = 165_615                                       # theory_850k row 9 payload per division
end_mult = 2 * n * (3 * n + 120) + n * n                # two double-and-add modular products + exact division
T += 2 * (pay_ticks - pay_old) + 2 * end_mult
end_peak = n + n + n + 280 + carries + 20               # d, y, z, m12 (~280 bits), carries
rows.append(("Q4 transposed integer cofactors in the reverse pass (S)", T, max(walk_peak, end_peak),
             f"walk peak {walk_peak}, end-phase peak {end_peak}"))

# Q5 (S!): m12 folded to 256 bits (Solinas) and the end multiplication done with one extra register by an in-place
# Montgomery product that borrows the tape-free rail wires dirty; end-phase peak d + y/z + m12 + carries
end_peak = n + (n + 1) + n + carries + 20
rows.append(("Q5 in-place end product with dirty borrowed wires (S!)", T, max(walk_peak, end_peak),
             f"walk peak {walk_peak}, end-phase peak {end_peak}"))

print(f"{'step':58s} {'T':>10s} {'Q':>6s} {'score':>8s}  note")
for name, t, q, note in rows:
    print(f"{name:58s} {t:10,.0f} {q:6d} {t * q / 1e9:7.2f}B  {note}")

# Q6 (T/S): carry blocks of 24 (carries 40 -> 32, +n/24 saved-carry erasures per add) and misc ancillas 40 -> 32
T += 2 * 305 * 3 * 4                                    # a few more block-boundary erasures per add
carries, misc = 32, 32
walk_peak = tape + n + 20 + carries + misc
end_peak = n + (n + 1) + n + carries + 20
q = max(walk_peak, end_peak)
print(f"{'Q6 carry blocks of 24, misc ancillas trimmed (T/S)':58s} {T:10,.0f} {q:6d} {T * q / 1e9:7.2f}B  walk peak {walk_peak}")
