#!/usr/bin/env python3
"""Can the leapfrog walk's branch letters be decoded instead of stored?

Model of one tick (leapfrog.rs header): target T, source B, both odd.
  three forced steps  T <- (T + s B)/2, s = +1 iff T = B (mod 4)
  fourth step: of T +- B exactly one is 0 mod 4 ("deep"); take it when
  v2(deep) <= 4, else the other ("flat"); strip e = v2(result) zeros.
A letter is decodable in reverse if the post-step state determines it.
Predictor tested: the predecessor of smallest magnitude.
"""
import random
import sys
from collections import Counter

P = 2**256 - 2**32 - 977


def v2(x):
    return (x & -x).bit_length() - 1


def tick(T, B, letters):
    for _ in range(3):
        s = 1 if (T - B) % 4 == 0 else -1
        new = (T + s * B) // 2
        letters.append(("forced", s, new, B, T))
        T = new
    deep_s = 1 if (T + B) % 4 == 0 else -1
    deep = T + deep_s * B
    if v2(deep) <= 4:
        s, value = deep_s, deep
    else:
        s, value = -deep_s, T - deep_s * B
    if value == 0:
        return None
    e = v2(value)                      # total halvings of this step, 1..4
    new = value >> e if value > 0 else -((-value) >> e)
    letters.append(("fourth", (s, e), new, B, T))
    return new


def walk(d, ticks=122):
    rails = [d if d % 2 else d + P, P]
    letters = []
    for t in range(ticks):
        target = t % 2
        new = tick(rails[target], rails[1 - target], letters)
        if new is None:
            break
        rails[target] = new
        if abs(rails[0]) == 1 and abs(rails[1]) == 1:
            break
    return letters


def decode(kind, after, B):
    if kind == "forced":
        options = [(s, 2 * after - s * B) for s in (1, -1)]
    else:
        options = [((s, e), (after << e) - s * B) for s in (1, -1) for e in range(1, 5)]
        options = [(letter, T) for letter, T in options if T % 2]
    return min(options, key=lambda item: abs(item[1]))[0]


if __name__ == "__main__" and "--envelope" not in sys.argv:
    rng = random.Random(1080)
    stats = Counter()
    for _ in range(400):
        for kind, letter, after, B, before in walk(rng.randrange(1, P)):
            stats[kind, decode(kind, after, B) == letter] += 1
    for kind in ("forced", "fourth"):
        ok, bad = stats[kind, True], stats[kind, False]
        print(f"{kind}: min-magnitude decoder correct {ok}/{ok + bad} = {ok / (ok + bad):.4f}")


def envelope_test(seed=1080, train=3000, test=1000):
    """Decode by the empirical width envelope: count candidates that fit."""
    rng = random.Random(seed)
    width = {}
    def steps(d):
        index = 0
        for kind, letter, after, B, before in walk(d):
            yield index, kind, letter, after, B, before
            index += 1
    for _ in range(train):
        for index, *_rest, before in steps(rng.randrange(1, P)):
            width[index] = max(width.get(index, 0), abs(before).bit_length())
    stats = Counter()
    for _ in range(test):
        for index, kind, letter, after, B, before in steps(rng.randrange(1, P)):
            if kind == "forced":
                options = [(s, 2 * after - s * B) for s in (1, -1)]
            else:
                options = [((s, e), (after << e) - s * B) for s in (1, -1) for e in range(1, 5)]
                options = [(l, T) for l, T in options if T % 2]
            fits = [l for l, T in options if abs(T).bit_length() <= width.get(index, 0)]
            stats[kind, "unique" if fits == [letter] else ("ambiguous" if letter in fits else "outside")] += 1
    return stats


if __name__ == "__main__" and "--envelope" in sys.argv:
    stats = envelope_test()
    for kind in ("forced", "fourth"):
        total = sum(v for (k, _), v in stats.items() if k == kind)
        print(kind, {o: f"{stats[kind, o] / total:.3f}" for o in ("unique", "ambiguous", "outside")})
