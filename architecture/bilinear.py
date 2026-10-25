"""GF(2) rank decomposition for a separated bilinear partial-product form.

For a^T M b, return M = sum_k u_k v_k^T. Each product of two
linear parities can be prepared with one CCX and CNOT conjugation.
This is standard GF(2) elimination, not a novel arithmetic algorithm.
"""


def factor(matrix):
    if not matrix:
        return []
    columns = len(matrix[0])
    if any(len(row) != columns or any(value not in (0, 1) for value in row) for row in matrix):
        raise ValueError("Matrix must be rectangular and binary")
    rows = [sum(value << index for index, value in enumerate(row)) for row in matrix]
    factors = []
    while any(rows):
        pivot = next(index for index, row in enumerate(rows) if row)
        v = rows[pivot]
        column = (v & -v).bit_length() - 1
        u = sum(((row >> column) & 1) << index for index, row in enumerate(rows))
        factors.append((u, v))
        for index in range(len(rows)):
            if u >> index & 1:
                rows[index] ^= v
    return factors


def monomials(matrix, left, right):
    if len(matrix) != len(left) or any(len(row) != len(right) for row in matrix):
        raise ValueError("Matrix dimensions do not match operand bit sets")
    if len(set(left + right)) != len(left) + len(right):
        raise ValueError("Left and right data controls must be distinct")
    return frozenset((1 << left[i]) | (1 << right[j]) for i, row in enumerate(matrix) for j, value in enumerate(row) if value)


def wire_factors(matrix, left, right):
    # Validate the operand partition even for the all-zero matrix.
    monomials(matrix, left, right)
    return tuple((tuple(wire for index, wire in enumerate(left) if u >> index & 1), tuple(wire for index, wire in enumerate(right) if v >> index & 1)) for u, v in factor(matrix))
