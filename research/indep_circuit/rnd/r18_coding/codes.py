#!/usr/bin/env python3
"""R18: tape codes for the Euclid walks, with real encode/decode round trips and the shared-register peak.

Symbol streams:
  classic Euclid (C0): one quotient q >= 1 per step
  radix-4 nearest Euclid (C1): per step the signed digits d_j in {-2..2} and the remainder sign
Codes:
  EG     Elias-gamma of q (C0)
  GKH    static Huffman over q (C0), probabilities from Gauss-Kuzmin, escape to Elias-gamma for q > 64
  FIX5   fixed log2(5) bits per digit + 2 flag bits per step (C1 baseline, as an upper bound)
  DH     static Huffman over C1 (digit, last-of-step) symbols, trained on a separate sample
Reported: total tape bits and shared peak = max over steps of bits(f) + bits(g) + tape so far; ok = round trip.
"""
import heapq
import math
import random
import sys
from collections import Counter

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from common import P, save, sweep  # noqa: E402
from r17_swapfree.euclid_variants import radix4_digits  # noqa: E402


def eg_enc(q):
    b = bin(q)[2:]
    return "0" * (len(b) - 1) + b


def eg_dec(bits, i):
    z = 0
    while bits[i + z] == "0":
        z += 1
    return int(bits[i + z:i + 2 * z + 1], 2), i + 2 * z + 1


def huffman(freqs):
    heap = [[w, i, [s, ""]] for i, (s, w) in enumerate(freqs.items())]
    heapq.heapify(heap)
    k = len(heap)
    while len(heap) > 1:
        lo, hi = heapq.heappop(heap), heapq.heappop(heap)
        for pair in lo[2:]:
            pair[1] = "0" + pair[1]
        for pair in hi[2:]:
            pair[1] = "1" + pair[1]
        heapq.heappush(heap, [lo[0] + hi[0], k] + lo[2:] + hi[2:])
        k += 1
    return {s: c for s, c in heap[0][2:]}


GK = {q: -math.log2(1 - 1 / (q + 1) ** 2) for q in range(1, 65)}
GK["esc"] = 1 - sum(GK.values())
GKH = huffman(GK)
GKH_DEC = {v: k for k, v in GKH.items()}


def gkh_enc(q):
    return GKH[q] if q <= 64 else GKH["esc"] + eg_enc(q)


def c1_symbols(d):
    f, g, out = P, d, []
    while g:
        digits, r = radix4_digits(f, g)
        for idx, (_, dj) in enumerate(digits):
            out.append((dj, idx == len(digits) - 1, (r < 0) if idx == len(digits) - 1 else False))
        f, g = g, abs(r)
    return out


def _train_dh(n=3000, seed=99):
    rnd = random.Random(seed)
    cnt = Counter()
    for _ in range(n):
        cnt.update(c1_symbols(rnd.randrange(1, P)))
    return huffman(cnt)


DH = _train_dh()
DH_DEC = {v: k for k, v in DH.items()}


def prefix_decode(bits, table):
    out, cur = [], ""
    for ch in bits:
        cur += ch
        if cur in table:
            out.append(table[cur])
            cur = ""
    assert cur == ""
    return out


def measure(d):
    res = {}
    # C0 streams
    f, g, tape_eg, tape_gk, pk_eg, pk_gk, qs, bits_eg, bits_gk = P, d, 0, 0, 0, 0, [], [], []
    while g:
        q, r = divmod(f, g)
        qs.append(q)
        e, h = eg_enc(q), gkh_enc(q)
        bits_eg.append(e)
        bits_gk.append(h)
        tape_eg += len(e)
        tape_gk += len(h)
        f, g = g, r
        pk_eg = max(pk_eg, f.bit_length() + g.bit_length() + tape_eg)
        pk_gk = max(pk_gk, f.bit_length() + g.bit_length() + tape_gk)
    s, i, dec = "".join(bits_eg), 0, []
    while i < len(s):
        q, i = eg_dec(s, i)
        dec.append(q)
    res["EG_ok"] = dec == qs
    res["EG_peak"] = pk_eg
    res["GKH_peak"] = pk_gk
    # C1 streams
    syms = c1_symbols(d)
    enc = "".join(DH[s] for s in syms)
    res["DH_ok"] = prefix_decode(enc, DH_DEC) == syms
    f, g, t_fix, t_dh, pk_fix, pk_dh, k = P, d, 0.0, 0, 0, 0, 0
    while g:
        digits, r = radix4_digits(f, g)
        for idx in range(len(digits)):
            t_fix += math.log2(5)
            t_dh += len(DH[syms[k]])
            k += 1
        t_fix += 2
        f, g = g, abs(r)
        pk_fix = max(pk_fix, f.bit_length() + g.bit_length() + t_fix)
        pk_dh = max(pk_dh, f.bit_length() + g.bit_length() + t_dh)
    res["FIX5_peak"] = round(pk_fix, 1)
    res["DH_peak"] = pk_dh
    return res


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    a = sweep(measure, n, seed)
    for k in ("EG", "GKH", "FIX5", "DH"):
        ok = a.get(f"{k}_ok", "-")
        print(f"{k:5s} shared peak max {a[f'{k}_peak']['max']} mean {a[f'{k}_peak']['mean']} q99.99 {a[f'{k}_peak']['q99_99']}  round trip {ok}")
    print("saved", save(f"r18_codes_n{n}_s{seed}", a))
