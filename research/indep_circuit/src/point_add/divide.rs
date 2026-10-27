//! In-place division y <- y / d (mod p) by half-delta divsteps (Bernstein-Yang), d kept.
//!
//! Rails (f, g) start at (p, d) as W = n + 2 bit two's-complement registers; g is the d register itself plus two
//! extension wires. 2*delta lives in a 12-bit signed register starting at 1. Per step (letters odd, swap on the tape):
//!   odd = g mod 2,  swap = odd and delta > 0
//!   if swap: (f, g) <- (g, f) and delta <- -delta
//!   g <- (g xor swap) + odd*f + swap   (= f - g on a swap, g + f when odd, g when even)
//!   g <- g / 2 (arithmetic shift by a SWAP rotation),  2*delta <- 2*delta + 2
//! The payload (a, b) starts at (0, y) with a*d = f*y and b*d = g*y (mod p) and follows the same letters mod p.
//! After S steps g = 0, f = +-1 and a = +-y/d. The sign is fixed from f's top bit, a is swapped onto the y wires
//! (b is 0 there), and the rails walk back to (p, d), erasing the tape.
use super::arith::*;
use super::builder::{emit_inverse, B};
use crate::circuit::QubitId;
use alloy_primitives::U256;
use super::rail_w::RAIL_W;

pub const DW: usize = 12;
/// Steps that use the zero-safe negation (the first swap comes after at most this many halvings of d,
/// except for d divisible by 2^SAFE_STEPS: probability 2^-64).
pub const SAFE_STEPS: usize = 64;
/// Pack the tape's ternary letters three steps to five bits.
pub const PACK: bool = true;
/// Merged signed payload update after the zero-safe steps.
pub const FAST_PAYLOAD: bool = true;

pub struct Rails {
    pub f: Vec<QubitId>,
    pub g: Vec<QubitId>,
    pub d: Vec<QubitId>,
}

/// Fixed-width core of a rails step on w+1 wires (both rails already sign-extended by one wire).
fn rails_core(b: &mut B, r: &Rails, t_odd: QubitId, t_swap: QubitId) {
    let w = r.g.len();
    b.label("rails_core");
    b.cx(r.g[0], t_odd);
    let ds = r.d[DW - 1];
    b.x(ds);
    b.ccx(t_odd, ds, t_swap);
    b.x(ds);
    for i in 0..w {
        b.cswap(t_swap, r.f[i], r.g[i]);
    }
    for &q in &r.g {
        b.cx(t_swap, q);
    }
    let m = b.alloc_n(w);
    for i in 0..w {
        b.and_compute(t_odd, r.f[i], m[i]);
    }
    add(b, &m, &r.g, t_swap, None);
    for i in 0..w {
        b.and_uncompute(t_odd, r.f[i], m[i]);
    }
    b.release_n(&m);
    // arithmetic shift right by one: g[0] is 0; rotate it to the top, then sign-extend
    for i in 0..w - 1 {
        b.swap(r.g[i], r.g[i + 1]);
    }
    b.cx(r.g[w - 2], r.g[w - 1]);
    // 2*delta <- (2*delta xor swap) + swap + 2
    for &q in &r.d {
        b.cx(t_swap, q);
    }
    let two = load_const(b, DW, U256::from(2u8), None);
    add(b, &two, &r.d, t_swap, None);
    unload_const(b, &two, U256::from(2u8), None);
}

/// Resize both rails to `w` wires: drop top wires that are sign copies (CX-erase, release) or add sign copies.
/// Dropping is exact while the walk stays inside the width table.
fn resize(b: &mut B, r: &mut Rails, w: usize) {
    b.label("resize");
    for v in [&mut r.f, &mut r.g] {
        while v.len() > w {
            let top = v.pop().unwrap();
            b.cx(v[w - 1], top);
            b.release(top);
        }
        while v.len() < w {
            let q = b.alloc();
            b.cx(v[v.len() - 1], q);
            v.push(q);
        }
    }
}

/// Forward step t: extend by one, core, resize to the next table width.
pub fn rails_step(b: &mut B, r: &mut Rails, w_next: usize, t_odd: QubitId, t_swap: QubitId) {
    let w = r.g.len();
    resize(b, r, w + 1);
    rails_core(b, r, t_odd, t_swap);
    resize(b, r, w_next);
}

/// Exact inverse of `rails_step` from width w_next back to width w.
pub fn rails_unstep(b: &mut B, r: &mut Rails, w: usize, t_odd: QubitId, t_swap: QubitId) {
    resize(b, r, w + 1);
    emit_inverse(b, |b| rails_core(b, r, t_odd, t_swap));
    resize(b, r, w);
}

/// One payload step: same letters on (a, b) mod p; `e` is b's zero extension wire.
pub fn payload_step(b: &mut B, pa: &[QubitId], pb: &[QubitId], e: QubitId, t_odd: QubitId, t_swap: QubitId, p: U256, zero_safe: bool) {
    for i in 0..pa.len() {
        b.cswap(t_swap, pa[i], pb[i]);
    }
    // b is 0 only while the rail it mirrors is p, i.e. up to the first swap (after <= SAFE_STEPS halvings of d)
    if zero_safe {
        cmod_neg_safe(b, pb, t_swap, p);
    } else {
        cmod_neg(b, pb, t_swap, p);
    }
    cmod_add(b, pb, pa, t_odd, p);
    mod_halve(b, pb, e, p);
}


/// The 3^j-weighted ternary letters of three steps: (odd, swap) pairs with swap => odd, trit = odd + swap.
fn trit_value(pairs: &[(bool, bool)]) -> u64 {
    pairs.iter().enumerate().map(|(j, &(o, s))| 3u64.pow(j as u32) * (o as u64 + s as u64)).sum()
}

/// XOR into the six letter wires the pattern of the code value (lookup over all 27 codes, temporary ANDs).
fn letters_from_code(b: &mut B, code: &[QubitId], pairs: &[(QubitId, QubitId)]) {
    for v in 0..27u64 {
        let tr: Vec<u64> = (0..3).map(|j| (v / 3u64.pow(j)) % 3).collect();
        if tr.iter().all(|&t| t == 0) {
            continue;
        }
        // eq = [code == v] by an AND ladder over the 5 code bits (X-conjugated zeros)
        for i in 0..5 {
            if (v >> i) & 1 == 0 {
                b.x(code[i]);
            }
        }
        let mut acc = code[0];
        let mut ladder = Vec::new();
        for i in 1..5 {
            let t = b.alloc();
            b.and_compute(acc, code[i], t);
            ladder.push((acc, code[i], t));
            acc = t;
        }
        for j in 0..3 {
            if tr[j] >= 1 {
                b.cx(acc, pairs[j].0);
            }
            if tr[j] == 2 {
                b.cx(acc, pairs[j].1);
            }
        }
        for &(x, y, t) in ladder.iter().rev() {
            b.and_uncompute(x, y, t);
            b.release(t);
        }
        for i in 0..5 {
            if (v >> i) & 1 == 0 {
                b.x(code[i]);
            }
        }
    }
}

/// Pack three steps' letters into a fresh 5-bit code (27 of 32 values); the six letter wires are released.
fn pack3(b: &mut B, pairs: &[(QubitId, QubitId)]) -> Vec<QubitId> {
    b.label("pack3");
    let code = b.alloc_n(5);
    for (j, &(o, s)) in pairs.iter().enumerate() {
        let w = U256::from(3u64.pow(j as u32));
        add_const(b, &code, w, Some(o));
        add_const(b, &code, w, Some(s));
    }
    letters_from_code(b, &code, pairs);
    for &(o, s) in pairs {
        b.release(o);
        b.release(s);
    }
    code
}

/// Inverse of `pack3`: fresh letter wires, the code is erased and released.
fn unpack3(b: &mut B, code: &[QubitId]) -> Vec<(QubitId, QubitId)> {
    b.label("unpack3");
    let pairs: Vec<(QubitId, QubitId)> = (0..3).map(|_| (b.alloc(), b.alloc())).collect();
    letters_from_code(b, code, &pairs);
    for (j, &(o, s)) in pairs.iter().enumerate().rev() {
        let w = U256::from(3u64.pow(j as u32));
        sub_const(b, code, w, Some(s));
        sub_const(b, code, w, Some(o));
    }
    b.release_n(code);
    pairs
}


/// Payload step for b != 0 (after the first swap): b <- (sigma b + odd a) / 2 (mod p), sigma = -1 on a swap.
/// s = (b xor swap) + odd*a + swap on n + 2 signed bits lies in (-p, 2p); one +-p correction (direction from the
/// sign, enable u = [s mod 2^(n+1) >= p]) brings it to [0, p). The flags are erased with w = [r >= odd*a]:
/// on a swap ng = [r > a] and u = ng; otherwise ng = 0 and u = not w.
pub fn payload_step_fast(b: &mut B, pa: &[QubitId], pb: &[QubitId], e: QubitId, t_odd: QubitId, t_swap: QubitId, p: U256) {
    b.label("payload_fast");
    let n = pa.len();
    for i in 0..n {
        b.cswap(t_swap, pa[i], pb[i]);
    }
    let e2 = b.alloc();
    let mut bx = pb.to_vec();
    bx.push(e);
    bx.push(e2);
    for &q in &bx {
        b.cx(t_swap, q);
    }
    let m = b.alloc_n(n);
    for i in 0..n {
        b.and_compute(t_odd, pa[i], m[i]);
    }
    let mz = b.alloc_n(2);
    let mut mx = m.clone();
    mx.extend(&mz);
    add(b, &mx, &bx, t_swap, None);
    let ng = b.alloc();
    b.cx(bx[n + 1], ng);
    let u = b.alloc();
    ge_const_flag(b, &bx[..n + 1], p, u);
    // r = s + p (ng) or s - p (not ng), when u: complement around the add when not ng
    b.x(ng);
    for &q in &bx {
        b.cx(ng, q);
    }
    add_const(b, &bx, p, Some(u));
    for &q in &bx {
        b.cx(ng, q);
    }
    b.x(ng);
    // erase the flags with w = [r >= m]
    // w = [r > m] on a swap (exact also for b = 0 at the first swap, where r = a), [r >= m] otherwise
    let w = b.alloc();
    b.x(t_swap);
    ge_flag_cin(b, &m, pb, t_swap, w);
    b.x(t_swap);
    b.ccx(t_swap, ng, u);
    b.x(t_swap);
    b.x(w);
    b.ccx(t_swap, w, u);
    b.x(w);
    b.x(t_swap);
    b.ccx(t_swap, w, ng);
    b.x(t_swap);
    ge_flag_cin(b, &m, pb, t_swap, w);
    b.x(t_swap);
    b.release(w);
    b.release(u);
    b.release(ng);
    b.release_n(&mz);
    for i in 0..n {
        b.and_uncompute(t_odd, pa[i], m[i]);
    }
    b.release_n(&m);
    b.release(e2);
    mod_halve(b, pb, e, p);
}

/// y <- y / x (mod p) in place; x is restored. `steps` must bound the divsteps count for n-bit inputs.
pub fn divide(b: &mut B, y: &[QubitId], x: &[QubitId], p: U256, steps: usize) {
    divide_w(b, y, x, p, steps, &|t| if x.len() == 256 { RAIL_W[t] as usize } else { x.len() + 2 });
}

pub fn divide_w(b: &mut B, y: &[QubitId], x: &[QubitId], p: U256, steps: usize, wt: &dyn Fn(usize) -> usize) {
    let n = x.len();
    let w0 = wt(0);
    let f = load_const(b, w0, p, None);
    let mut g = x.to_vec();
    g.extend(b.alloc_n(w0 - n));
    let d = load_const(b, DW, U256::from(1u8), None);
    let mut r = Rails { f, g, d };
    let pa = b.alloc_n(n);
    let e = b.alloc();
    // tape: packed groups of three steps (5-bit codes) and the unpacked letters of the last partial group
    let mut codes: Vec<Vec<QubitId>> = Vec::new();
    let mut pending: Vec<(QubitId, QubitId)> = Vec::new();
    for t in 0..steps {
        let (to, ts) = (b.alloc(), b.alloc());
        b.label("step");
        rails_step(b, &mut r, wt(t + 1), to, ts);
        if !FAST_PAYLOAD {
            payload_step(b, &pa, y, e, to, ts, p, t < SAFE_STEPS);
        } else {
            payload_step_fast(b, &pa, y, e, to, ts, p);
        }
        pending.push((to, ts));
        if PACK && pending.len() == 3 {
            codes.push(pack3(b, &pending));
            pending.clear();
        }
    }
    // a = +-y/x, b (= y wires) = 0: fix the sign from f's top bit, then move a onto the y wires
    b.label("signfix");
    let top = r.f[r.f.len() - 1];
    cmod_neg(b, &pa, top, p);
    for i in 0..n {
        b.swap(pa[i], y[i]);
    }
    b.release_n(&pa);
    b.release(e);
    let mut t = steps;
    while t > 0 {
        if pending.is_empty() {
            pending = unpack3(b, &codes.pop().unwrap());
        }
        let (to, ts) = pending.pop().unwrap();
        t -= 1;
        b.label("unstep");
        rails_unstep(b, &mut r, wt(t), to, ts);
        b.release(to);
        b.release(ts);
    }
    b.label("unload");
    unload_const(b, &r.d, U256::from(1u8), None);
    // d is back on g (0 <= d < 2^n: the wires above n are 0); put it on the original x wires
    b.release_n(&r.g[n..].to_vec());
    r.g.truncate(n);
    for i in 0..n {
        if r.g[i] == x[i] {
            continue;
        }
        if b.is_free(x[i]) {
            let q = b.alloc_id(x[i]);
            b.swap(r.g[i], q);
            b.release(r.g[i]);
            r.g[i] = q;
        } else if let Some(j) = r.g.iter().position(|&q| q == x[i]) {
            b.swap(r.g[i], r.g[j]);
            r.g.swap(i, j);
        } else {
            let k = r.f.iter().position(|&q| q == x[i]).expect("x wire held outside the rails");
            b.swap(r.g[i], r.f[k]);
            std::mem::swap(&mut r.g[i], &mut r.f[k]);
        }
    }
    unload_const(b, &r.f, p, None);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::circuit::analyze_ops;
    use crate::sim::Simulator;
    use sha3::digest::{ExtendableOutput, Update};

    fn modinv(a: u128, p: u128) -> u128 {
        let (mut r0, mut r1, mut s0, mut s1) = (p as i128, a as i128, 0i128, 1i128);
        while r1 != 0 {
            let q = r0 / r1;
            (r0, r1) = (r1, r0 - q * r1);
            (s0, s1) = (s1, s0 - q * s1);
        }
        s0.rem_euclid(p as i128) as u128
    }

    fn set(sim: &mut Simulator<impl sha3::digest::XofReader>, reg: &[QubitId], v: u128, shot: usize) {
        for (i, &q) in reg.iter().enumerate() {
            if (v >> i) & 1 == 1 {
                *sim.qubit_mut(q) |= 1 << shot;
            }
        }
    }
    fn get(sim: &Simulator<impl sha3::digest::XofReader>, reg: &[QubitId], shot: usize) -> u128 {
        reg.iter().enumerate().map(|(i, &q)| (((sim.qubit(q) >> shot) & 1) as u128) << i).sum()
    }

    #[test]
    fn divide_small_prime() {
        let n = 61;
        let p: u128 = (1 << 61) - 1;
        let pu = U256::from(p);
        let b = &mut B::new();
        let x = b.alloc_n(n);
        let y = b.alloc_n(n);
        divide_w(b, &y, &x, pu, 3 * n + 10, &|t| if t < 80 { n + 2 } else { (n + 2).saturating_sub((t - 80) / 3).max(8) });
        let (nq, nb, _, _) = analyze_ops(b.ops.iter());
        let mut h = sha3::Shake256::default();
        h.update(b"test");
        let mut xof = h.finalize_xof();
        let mut sim = Simulator::new(nq as usize, nb as usize, &mut xof);
        let mut s: u64 = 12345;
        let mut rnd = || { s ^= s << 13; s ^= s >> 7; s ^= s << 17; (s as u128 * 0x9E37_79B9) % (p - 1) + 1 };
        let cases: Vec<(u128, u128)> = (0..64).map(|i| match i { 0 => (1, rnd()), 1 => (p - 1, p - 1), 2 => (2, rnd()), _ => (rnd(), rnd()) }).collect();
        for (shot, &(xv, yv)) in cases.iter().enumerate() {
            set(&mut sim, &x, xv, shot);
            set(&mut sim, &y, yv, shot);
        }
        for (k, o) in b.ops.iter().enumerate() {
            if o.kind == crate::circuit::OperationType::R && sim.qubit(o.q_target) != 0 {
                let labs: Vec<_> = b.labels.iter().filter(|(i, _)| *i <= k).rev().take(4).map(|x| x.1).collect();
                let nsteps = b.labels.iter().filter(|(i, l)| *i <= k && *l == "step").count();
                let nun = b.labels.iter().filter(|(i, l)| *i <= k && *l == "unstep").count();
                panic!("R on nonzero qubit {} at op {k} (labels {labs:?}, steps {nsteps}, unsteps {nun})", o.q_target.0);
            }
            sim.apply_iter(std::iter::once(o));
        }
        let mut bad = 0;
        for (shot, &(xv, yv)) in cases.iter().enumerate() {
            let want = yv * modinv(xv, p) % p;
            let (gx, gy) = (get(&sim, &x, shot), get(&sim, &y, shot));
            if gx != xv || gy != want {
                bad += 1;
                eprintln!("shot {shot}: x {xv} -> {gx}, y {yv} -> {gy}, want {want}");
            }
        }
        let others: u64 = (0..nq).filter(|&q| !x.iter().chain(y.iter()).any(|r| r.0 == q)).map(|q| sim.qubit(QubitId(q))).fold(0, |a, v| a | v);
        eprintln!("qubits {nq}, toffoli {}, ancilla garbage {:#x}, phase {:#x}", sim.stats.toffoli_gates / 64, others, sim.phase);
        assert_eq!(bad, 0);
        assert_eq!(others, 0);
        assert_eq!(sim.phase, 0);
    }

    fn set256(sim: &mut Simulator<impl sha3::digest::XofReader>, reg: &[QubitId], v: U256, shot: usize) {
        for (i, &q) in reg.iter().enumerate() {
            if v.bit(i) {
                *sim.qubit_mut(q) |= 1 << shot;
            }
        }
    }
    fn get256(sim: &Simulator<impl sha3::digest::XofReader>, reg: &[QubitId], shot: usize) -> U256 {
        let mut v = U256::ZERO;
        for (i, &q) in reg.iter().enumerate() {
            if (sim.qubit(q) >> shot) & 1 == 1 {
                v.set_bit(i, true);
            }
        }
        v
    }

    #[test]
    fn divide_and_multiply_256() {
        let p = super::super::P;
        for inverse in [false, true] {
            let b = &mut B::new();
            let x = b.alloc_n(256);
            let y = b.alloc_n(256);
            if inverse {
                emit_inverse(b, |b| divide(b, &y, &x, p, super::super::STEPS));
            } else {
                divide(b, &y, &x, p, super::super::STEPS);
            }
            let (nq, nb, _, _) = analyze_ops(b.ops.iter());
            let mut h = sha3::Shake256::default();
            h.update(b"t256");
            let mut xof = h.finalize_xof();
            let mut sim = Simulator::new(nq as usize, nb as usize, &mut xof);
            let mut s: u64 = 0x1234_5678_9abc_def1;
            let mut rnd = || {
                let mut v = U256::ZERO;
                for k in 0..4 {
                    s ^= s << 13; s ^= s >> 7; s ^= s << 17;
                    v |= U256::from(s) << (64 * k);
                }
                v % (p - U256::from(1u8)) + U256::from(1u8)
            };
            let cases: Vec<(U256, U256)> = (0..64).map(|i| if i == 0 { (U256::from(1u8), rnd()) } else if i == 1 { (p - U256::from(1u8), rnd()) } else { (rnd(), rnd()) }).collect();
            for (shot, &(xv, yv)) in cases.iter().enumerate() {
                set256(&mut sim, &x, xv, shot);
                set256(&mut sim, &y, yv, shot);
            }
            sim.apply_iter(b.ops.iter());
            let mut bad = 0;
            for (shot, &(xv, yv)) in cases.iter().enumerate() {
                let want = if inverse { yv.mul_mod(xv, p) } else { yv.mul_mod(xv.inv_mod(p).unwrap(), p) };
                if get256(&sim, &x, shot) != xv || get256(&sim, &y, shot) != want {
                    bad += 1;
                    eprintln!("bad shot {shot}: x {xv:#x} y {yv:#x}");
                }
            }
            let others: u64 = (0..nq).filter(|&q| !x.iter().chain(y.iter()).any(|r| r.0 == q)).map(|q| sim.qubit(QubitId(q))).fold(0, |a, v| a | v);
            eprintln!("inverse {inverse}: qubits {nq}, toffoli {}, bad {bad}, garbage {others:#x}, phase {:#x}", sim.stats.toffoli_gates / 64, sim.phase);
            assert_eq!((bad, others, sim.phase), (0, 0, 0));
        }
    }
}
