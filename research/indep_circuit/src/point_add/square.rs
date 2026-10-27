//! x <- x - y^2 (mod p) for p = 2^256 - c, c = 2^32 + 977 (Solinas form), from textbook pieces:
//!   acc = y^2 as a 512-bit integer by symmetric schoolbook rows (row k: y_k at 2^(2k), y_k y_j at 2^(k+j+1)),
//!   y^2 = H 2^256 + L = L + H c (mod p);  T = H c = (H << 32) + 977 H;  T = Th 2^256 + Tl = Tl + Th c (mod p).
//! x -= L, x -= Tl, x -= Th c (each a modular subtraction), then everything is uncomputed in reverse.
//! L or Tl >= p (probability ~2^-224) would break the modular subtraction's input range.
use super::arith::*;
use super::builder::{emit_inverse, B};
use crate::circuit::QubitId;
use alloy_primitives::U256;

const C_LOW: [usize; 6] = [0, 4, 6, 7, 8, 9]; // 977 = 0b1111010001

/// acc (2n zero wires) <- y^2.
pub fn square_into(b: &mut B, y: &[QubitId], acc: &[QubitId]) {
    b.label("square_into");
    let n = y.len();
    for k in 0..n {
        // operand at offset 2k: [y_k, 0, y_k y_{k+1}, ..., y_k y_{n-1}], window up to bit n + k + 2
        let hi = (n + k + 2).min(2 * n);
        let w = hi - 2 * k;
        let mut op: Vec<QubitId> = Vec::with_capacity(w);
        let mut masks = Vec::new();
        let mut zeros = Vec::new();
        for pos in 0..w {
            if pos == 0 {
                op.push(y[k]);
            } else if pos >= 2 && k + pos - 1 < n {
                let j = k + pos - 1;
                let m = b.alloc();
                b.and_compute(y[k], y[j], m);
                masks.push((j, m));
                op.push(m);
            } else {
                let z = b.alloc();
                zeros.push(z);
                op.push(z);
            }
        }
        let cin = b.alloc();
        add(b, &op, &acc[2 * k..hi], cin, None);
        b.release(cin);
        for (j, m) in masks {
            b.and_uncompute(y[k], y[j], m);
            b.release(m);
        }
        b.release_n(&zeros);
    }
}

/// t (zero wires, len >= h.len() + 34) <- h * c = (h << 32) + 977 h.
fn times_c_into(b: &mut B, h: &[QubitId], t: &[QubitId]) {
    let m = h.len();
    for i in 0..m {
        b.cx(h[i], t[i + 32]);
    }
    for &s in &C_LOW {
        // t[s..] += h, with the carry running to the top of t
        let w = t.len() - s;
        let mut op = h.to_vec();
        let zs = b.alloc_n(w - m);
        op.extend(&zs);
        let cin = b.alloc();
        add(b, &op, &t[s..], cin, None);
        b.release(cin);
        b.release_n(&zs);
    }
}

pub fn mod_sub_square(b: &mut B, x: &[QubitId], y: &[QubitId], p: U256) {
    let n = y.len();
    let acc = b.alloc_n(2 * n);
    let t = b.alloc_n(n + 34);
    let u = b.alloc_n(34 + 34);
    let compute = |b: &mut B| {
        square_into(b, y, &acc);
        times_c_into(b, &acc[n..], &t);
        times_c_into(b, &t[n..], &u);
    };
    compute(b);
    mod_sub(b, x, &acc[..n], p);
    mod_sub(b, x, &t[..n], p);
    let mut uu = u.clone();
    let zs = b.alloc_n(n - uu.len());
    uu.extend(&zs);
    mod_sub(b, x, &uu, p);
    b.release_n(&zs);
    emit_inverse(b, compute);
    b.release_n(&u);
    b.release_n(&t);
    b.release_n(&acc);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::circuit::analyze_ops;
    use crate::sim::Simulator;
    use sha3::digest::{ExtendableOutput, Update};

    #[test]
    fn sub_square_256() {
        let p = super::super::P;
        let b = &mut B::new();
        let x = b.alloc_n(256);
        let y = b.alloc_n(256);
        mod_sub_square(b, &x, &y, p);
        let (nq, nb, _, _) = analyze_ops(b.ops.iter());
        let mut h = sha3::Shake256::default();
        h.update(b"sq");
        let mut xof = h.finalize_xof();
        let mut sim = Simulator::new(nq as usize, nb as usize, &mut xof);
        let mut s: u64 = 0xdead_beef_1234_5678;
        let mut rnd = || {
            let mut v = U256::ZERO;
            for k in 0..4 {
                s ^= s << 13; s ^= s >> 7; s ^= s << 17;
                v |= U256::from(s) << (64 * k);
            }
            v % p
        };
        let cases: Vec<(U256, U256)> = (0..64).map(|_| (rnd(), rnd())).collect();
        let set = |sim: &mut Simulator<_>, reg: &[QubitId], v: U256, shot: usize| for (i, &q) in reg.iter().enumerate() { if v.bit(i) { *sim.qubit_mut(q) |= 1 << shot; } };
        for (shot, &(xv, yv)) in cases.iter().enumerate() {
            set(&mut sim, &x, xv, shot);
            set(&mut sim, &y, yv, shot);
        }
        sim.apply_iter(b.ops.iter());
        let get = |sim: &Simulator<_>, reg: &[QubitId], shot: usize| { let mut v = U256::ZERO; for (i, &q) in reg.iter().enumerate() { if (sim.qubit(q) >> shot) & 1 == 1 { v.set_bit(i, true); } } v };
        let mut bad = 0;
        for (shot, &(xv, yv)) in cases.iter().enumerate() {
            let want = xv.add_mod(p - yv.mul_mod(yv, p), p);
            if get(&sim, &x, shot) != xv.add_mod(U256::ZERO, p).add_mod(p - yv.mul_mod(yv, p), p) % p || get(&sim, &y, shot) != yv {
                bad += 1;
                eprintln!("bad {shot}: want {want:#x}");
            }
        }
        let others: u64 = (0..nq).filter(|&q| !x.iter().chain(y.iter()).any(|r| r.0 == q)).map(|q| sim.qubit(QubitId(q))).fold(0, |a, v| a | v);
        eprintln!("square: qubits {nq}, toffoli {}, bad {bad}, garbage {others:#x}, phase {:#x}", sim.stats.toffoli_gates / 64, sim.phase);
        assert_eq!((bad, others, sim.phase), (0, 0, 0));
    }
}
