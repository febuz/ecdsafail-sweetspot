//! Textbook reversible arithmetic on little-endian qubit registers.
//! Adders are Cuccaro et al. (2004) MAJ/UMA ripple adders (2n Toffoli, the carry-in wire is restored);
//! comparators compute only the carry chain and undo it; modular operations follow Vedral-Barenco-Ekert.
//! Every function here is built from X, CX, CCX, SWAP only, so `emit_inverse` can reverse it.
use super::builder::B;
use crate::circuit::{BitId, QubitId};
use alloy_primitives::U256;

/// Window of the approximate comparators (bits). A compare errs only when both sides agree on these top bits.
pub const WIN: usize = 40;

fn maj(b: &mut B, x: QubitId, y: QubitId, z: QubitId) {
    b.cx(z, y);
    b.cx(z, x);
    b.ccx(x, y, z);
}
fn uma(b: &mut B, x: QubitId, y: QubitId, z: QubitId) {
    b.ccx(x, y, z);
    b.cx(z, x);
    b.cx(x, y);
}
fn inv_maj(b: &mut B, x: QubitId, y: QubitId, z: QubitId) {
    b.ccx(x, y, z);
    b.cx(z, x);
    b.cx(z, y);
}

/// acc <- acc + a + cin (mod 2^n). `a` and `cin` are unchanged. Optional carry-out XORed into `cout`.
pub fn add_cuccaro(b: &mut B, a: &[QubitId], acc: &[QubitId], cin: QubitId, cout: Option<QubitId>) {
    let n = acc.len();
    assert_eq!(a.len(), n);
    maj(b, cin, acc[0], a[0]);
    for i in 1..n {
        maj(b, a[i - 1], acc[i], a[i]);
    }
    if let Some(c) = cout {
        b.cx(a[n - 1], c);
    }
    for i in (1..n).rev() {
        uma(b, a[i - 1], acc[i], a[i]);
    }
    uma(b, cin, acc[0], a[0]);
}

/// flag ^= carry-out of (acc + a + cin); acc, a, cin unchanged (2n Toffoli).
pub fn carry_flag_cuccaro(b: &mut B, a: &[QubitId], acc: &[QubitId], cin: QubitId, flag: QubitId) {
    let n = acc.len();
    maj(b, cin, acc[0], a[0]);
    for i in 1..n {
        maj(b, a[i - 1], acc[i], a[i]);
    }
    b.cx(a[n - 1], flag);
    for i in (1..n).rev() {
        inv_maj(b, a[i - 1], acc[i], a[i]);
    }
    inv_maj(b, cin, acc[0], a[0]);
}


/// Gidney (2018) ripple adder: acc <- acc + a + cin (mod 2^n), carries in temporary ANDs (n - 1 Toffoli, n - 1
/// ancillas), erased by X-measurement. Optional carry-out XORed into `cout` (one more AND).
pub fn add(b: &mut B, a: &[QubitId], acc: &[QubitId], cin: QubitId, cout: Option<QubitId>) {
    let n = acc.len();
    assert_eq!(a.len(), n);
    let top = if cout.is_some() { n } else { n - 1 };
    let mut c: Vec<QubitId> = vec![cin];
    for i in 0..top {
        let ci = c[i];
        b.cx(ci, a[i]);
        b.cx(ci, acc[i]);
        let t = b.alloc();
        b.and_compute(a[i], acc[i], t);
        b.cx(ci, t);
        c.push(t);
    }
    if let Some(co) = cout {
        b.cx(c[n], co);
        // undo the top stage (it only produced the carry-out)
        let i = n - 1;
        b.cx(c[i], c[n]);
        b.and_uncompute(a[i], acc[i], c[n]);
        b.release(c[n]);
        b.cx(c[i], a[i]);
        b.cx(c[i], acc[i]);
    }
    // top sum bit: acc[n-1] ^= a[n-1] ^ c[n-1]
    b.cx(c[n - 1], acc[n - 1]);
    b.cx(a[n - 1], acc[n - 1]);
    for i in (0..n - 1).rev() {
        b.cx(c[i], c[i + 1]);
        b.and_uncompute(a[i], acc[i], c[i + 1]);
        b.release(c[i + 1]);
        b.cx(c[i], a[i]);
        b.cx(a[i], acc[i]);
    }
}

/// flag ^= carry-out of (acc + a + cin); acc, a, cin unchanged (n Toffoli, carries erased by measurement).
pub fn carry_flag(b: &mut B, a: &[QubitId], acc: &[QubitId], cin: QubitId, flag: QubitId) {
    let n = acc.len();
    let mut c: Vec<QubitId> = vec![cin];
    for i in 0..n {
        let ci = c[i];
        b.cx(ci, a[i]);
        b.cx(ci, acc[i]);
        let t = b.alloc();
        b.and_compute(a[i], acc[i], t);
        b.cx(ci, t);
        c.push(t);
    }
    b.cx(c[n], flag);
    for i in (0..n).rev() {
        b.cx(c[i], c[i + 1]);
        b.and_uncompute(a[i], acc[i], c[i + 1]);
        b.release(c[i + 1]);
        b.cx(c[i], a[i]);
        b.cx(c[i], acc[i]);
    }
}

/// acc <- acc - a (mod 2^n): complement, add, complement.
pub fn sub(b: &mut B, a: &[QubitId], acc: &[QubitId], cin: QubitId) {
    for &q in acc {
        b.x(q);
    }
    add(b, a, acc, cin, None);
    for &q in acc {
        b.x(q);
    }
}

/// A register holding the constant c (n bits), loaded with X gates or, with `ctrl`, with CX from ctrl.
pub fn load_const(b: &mut B, n: usize, c: U256, ctrl: Option<QubitId>) -> Vec<QubitId> {
    let t = b.alloc_n(n);
    for i in 0..n {
        if i < 256 && c.bit(i) {
            match ctrl {
                Some(q) => b.cx(q, t[i]),
                None => b.x(t[i]),
            }
        }
    }
    t
}
pub fn unload_const(b: &mut B, t: &[QubitId], c: U256, ctrl: Option<QubitId>) {
    for i in 0..t.len() {
        if i < 256 && c.bit(i) {
            match ctrl {
                Some(q) => b.cx(q, t[i]),
                None => b.x(t[i]),
            }
        }
    }
    b.release_n(t);
}

#[derive(Clone, Copy)]
enum Kb {
    Zero,
    One,
    Q(QubitId),
}

/// Carry chain of acc + k (+ nothing else) with Gidney temporary ANDs. Bits of k are classical (no wire) or a
/// quantum wire. With `sum`, acc becomes acc + k (mod 2^n); with `flag`, the carry-out is XORed into it.
fn const_chain(b: &mut B, acc: &[QubitId], k: &[Kb], flag: Option<QubitId>, sum: bool) {
    let n = acc.len();
    let top = if flag.is_some() { n } else { n - 1 };
    let mut c: Vec<Option<QubitId>> = vec![None];
    for i in 0..top {
        let t = match (k[i], c[i]) {
            (Kb::Zero, None) => None,
            (Kb::One, None) => {
                let t = b.alloc();
                b.cx(acc[i], t);
                Some(t)
            }
            (Kb::Q(a), None) => {
                let t = b.alloc();
                b.and_compute(a, acc[i], t);
                Some(t)
            }
            (Kb::Zero, Some(ci)) => {
                let t = b.alloc();
                b.and_compute(acc[i], ci, t);
                Some(t)
            }
            (Kb::One, Some(ci)) => {
                let t = b.alloc();
                b.x(acc[i]);
                b.x(ci);
                b.and_compute(acc[i], ci, t);
                b.x(acc[i]);
                b.x(ci);
                b.x(t);
                Some(t)
            }
            (Kb::Q(a), Some(ci)) => {
                b.cx(ci, a);
                b.cx(ci, acc[i]);
                let t = b.alloc();
                b.and_compute(a, acc[i], t);
                b.cx(ci, t);
                Some(t)
            }
        };
        c.push(t);
    }
    if let Some(fl) = flag {
        if let Some(cn) = c[n] {
            b.cx(cn, fl);
        }
    } else if sum {
        let i = n - 1;
        match k[i] {
            Kb::Zero => {}
            Kb::One => b.x(acc[i]),
            Kb::Q(a) => b.cx(a, acc[i]),
        }
        if let Some(ci) = c[i] {
            b.cx(ci, acc[i]);
        }
    }
    for i in (0..top).rev() {
        // erase c[i+1]
        match (k[i], c[i], c[i + 1]) {
            (_, _, None) => {}
            (Kb::One, None, Some(t)) => {
                b.cx(acc[i], t);
                b.release(t);
            }
            (Kb::Q(a), None, Some(t)) => {
                b.and_uncompute(a, acc[i], t);
                b.release(t);
            }
            (Kb::Zero, Some(ci), Some(t)) => {
                b.and_uncompute(acc[i], ci, t);
                b.release(t);
            }
            (Kb::One, Some(ci), Some(t)) => {
                b.x(t);
                b.x(acc[i]);
                b.x(ci);
                b.and_uncompute(acc[i], ci, t);
                b.x(acc[i]);
                b.x(ci);
                b.release(t);
            }
            (Kb::Q(a), Some(ci), Some(t)) => {
                b.cx(ci, t);
                b.and_uncompute(a, acc[i], t);
                b.release(t);
                b.cx(ci, a);
                if !sum {
                    b.cx(ci, acc[i]);
                }
            }
            (Kb::Zero, None, Some(_)) => unreachable!(),
        }
        if sum {
            match k[i] {
                Kb::Zero => {}
                Kb::One => b.x(acc[i]),
                Kb::Q(a) => b.cx(a, acc[i]),
            }
            if let Some(ci) = c[i] {
                if !matches!(k[i], Kb::Q(_)) {
                    b.cx(ci, acc[i]);
                }
            }
        }
    }
}

fn two_pow(n: usize) -> U256 {
    if n >= 256 { U256::ZERO } else { U256::from(1u8) << n }
}

/// The n low bits of c (c < 2^256; bits >= 256 are 0).
fn bits_of(c: U256, n: usize) -> Vec<bool> {
    (0..n).map(|i| i < 256 && c.bit(i)).collect()
}

/// Two's complement negation of an n-bit vector: 2^n - v (mod 2^n).
fn neg_bits(v: &[bool]) -> Vec<bool> {
    let mut out = Vec::with_capacity(v.len());
    let mut carry = true;
    for &x in v {
        let y = !x;
        out.push(y ^ carry);
        carry &= y;
    }
    out
}

/// acc <- acc + c (mod 2^n), optionally controlled. Controlled constants need one wire per set bit, so a dense
/// constant is added as the subtraction of its sparse complement 2^n - c.
pub fn add_const(b: &mut B, acc: &[QubitId], c: U256, ctrl: Option<QubitId>) {
    let n = acc.len();
    let cb = bits_of(c, n);
    if !cb.iter().any(|&x| x) {
        return;
    }
    let nb = neg_bits(&cb);
    let pc = |v: &[bool]| v.iter().filter(|&&x| x).count();
    if ctrl.is_some() && pc(&nb) < pc(&cb) {
        for &q in acc {
            b.x(q);
        }
        add_bits_raw(b, acc, &nb, ctrl);
        for &q in acc {
            b.x(q);
        }
    } else {
        add_bits_raw(b, acc, &cb, ctrl);
    }
}

fn add_bits_raw(b: &mut B, acc: &[QubitId], c: &[bool], ctrl: Option<QubitId>) {
    let mut wires = Vec::new();
    let k: Vec<Kb> = c
        .iter()
        .map(|&bit| {
            if bit {
                match ctrl {
                    None => Kb::One,
                    Some(q) => {
                        let w = b.alloc();
                        b.cx(q, w);
                        wires.push(w);
                        Kb::Q(w)
                    }
                }
            } else {
                Kb::Zero
            }
        })
        .collect();
    const_chain(b, acc, &k, None, true);
    if let Some(q) = ctrl {
        for &w in &wires {
            b.cx(q, w);
            b.release(w);
        }
    }
}

/// acc <- acc - c (mod 2^n), optionally controlled.
pub fn sub_const(b: &mut B, acc: &[QubitId], c: U256, ctrl: Option<QubitId>) {
    for &q in acc {
        b.x(q);
    }
    add_const(b, acc, c, ctrl);
    for &q in acc {
        b.x(q);
    }
}

/// flag ^= [acc >= c] for an n-bit unsigned acc (carry of acc + 2^n - c), classical constant, no constant wires.
pub fn ge_const_flag(b: &mut B, acc: &[QubitId], c: U256, flag: QubitId) {
    b.label("ge_const_flag");
    let n = acc.len();
    if n >= 128 && WIN < n && c > U256::from(1u8) {
        // top-window compare: exact unless acc agrees with c on the top WIN bits
        let s = n - WIN;
        let ct = c >> s;
        return ge_const_flag(b, &acc[s..], ct, flag);
    }
    if c == U256::ZERO {
        b.x(flag);
        return;
    }
    let k = two_pow(n).wrapping_sub(c);
    let kb: Vec<Kb> = (0..n).map(|i| if i < 256 && k.bit(i) { Kb::One } else { Kb::Zero }).collect();
    const_chain(b, acc, &kb, Some(flag), false);
}

/// flag ^= carry of (acc + ~a + cin): [acc >= a] when cin = 1, [acc > a] when cin = 0 (top window for wide
/// registers, exact whenever the two values are equal or differ in the window).
pub fn ge_flag_cin(b: &mut B, a: &[QubitId], acc: &[QubitId], cin: QubitId, flag: QubitId) {
    b.label("ge_flag_cin");
    if acc.len() >= 128 && WIN < acc.len() {
        let s = acc.len() - WIN;
        return ge_flag_cin(b, &a[s..], &acc[s..], cin, flag);
    }
    for &q in a {
        b.x(q);
    }
    carry_flag(b, a, acc, cin, flag);
    for &q in a {
        b.x(q);
    }
}

/// flag ^= [acc >= a] for n-bit unsigned registers (carry of acc + ~a + 1).
pub fn ge_flag(b: &mut B, a: &[QubitId], acc: &[QubitId], flag: QubitId) {
    b.label("ge_flag");
    if acc.len() >= 128 && WIN < acc.len() {
        // top-window compare: exact unless acc and a agree on the top WIN bits
        let s = acc.len() - WIN;
        return ge_flag(b, &a[s..], &acc[s..], flag);
    }
    for &q in a {
        b.x(q);
    }
    let one = b.alloc();
    b.x(one);
    carry_flag(b, a, acc, one, flag);
    b.x(one);
    b.release(one);
    for &q in a {
        b.x(q);
    }
}

/// acc <- acc + a (mod p), acc and a in [0, p), n bits each. Compare-first: s = acc + a (n + 1 bits),
/// f = [s >= p], s -= f p, then f = [result < a] is erased with a comparison.
pub fn mod_add(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
    b.label("mod_add");
    let e = b.alloc();
    let za = b.alloc();
    let z = b.alloc();
    let mut accx = acc.to_vec();
    accx.push(e);
    let mut ax = a.to_vec();
    ax.push(za);
    add(b, &ax, &accx, z, None);
    let f = b.alloc();
    ge_const_flag(b, &accx, p, f);
    sub_const(b, &accx, p, Some(f));
    // f = 1 iff reduced iff result < a
    ge_flag(b, a, acc, f);
    b.x(f);
    b.release(f);
    b.release(z);
    b.release(za);
    b.release(e);
}

/// acc <- acc + ctrl * a (mod p).
pub fn cmod_add(b: &mut B, acc: &[QubitId], a: &[QubitId], ctrl: QubitId, p: U256) {
    let m = b.alloc_n(a.len());
    for i in 0..a.len() {
        b.and_compute(ctrl, a[i], m[i]);
    }
    mod_add(b, acc, &m, p);
    for i in 0..a.len() {
        b.and_uncompute(ctrl, a[i], m[i]);
    }
    b.release_n(&m);
}

/// v <- -v (mod p) when ctrl (v in [1, p); v = 0 would become p).
pub fn cmod_neg(b: &mut B, v: &[QubitId], ctrl: QubitId, p: U256) {
    b.label("cmod_neg");
    for &q in v {
        b.cx(ctrl, q);
    }
    add_const(b, v, p + U256::from(1u8), Some(ctrl));
}

/// v <- v / 2 (mod p) in place on the n wires `v` plus one zero wire `e` (returned to zero).
/// Odd v gets p added, then the n+1 wires rotate down by one (SWAPs, no Toffoli); the parity flag is erased
/// with a comparison against (p + 1) / 2.
pub fn mod_halve(b: &mut B, v: &[QubitId], e: QubitId, p: U256) {
    b.label("mod_halve");
    let c = b.alloc();
    b.cx(v[0], c);
    let mut vx = v.to_vec();
    vx.push(e);
    add_const(b, &vx, p, Some(c));
    for i in 0..v.len() {
        b.swap(vx[i], vx[i + 1]);
    }
    ge_const_flag(b, v, (p + U256::from(1u8)) >> 1, c);
    b.release(c);
}

/// Load classical bits into a fresh register (CX-free: classically conditioned X).
pub fn load_bits(b: &mut B, bits: &[BitId]) -> Vec<QubitId> {
    let t = b.alloc_n(bits.len());
    for i in 0..bits.len() {
        b.x_if(t[i], bits[i]);
    }
    t
}
pub fn unload_bits(b: &mut B, t: &[QubitId], bits: &[BitId]) {
    for i in 0..bits.len() {
        b.x_if(t[i], bits[i]);
    }
    b.release_n(t);
}

/// v <- -v (mod p) when ctrl, mapping 0 to 0 (the plain version maps 0 to p): after the complement-add, a result
/// equal to p is cleared, and the flag that did it is erased with a zero test of the result.
pub fn cmod_neg_safe(b: &mut B, v: &[QubitId], ctrl: QubitId, p: U256) {
    b.label("cmod_neg_safe");
    cmod_neg(b, v, ctrl, p);
    let fl = b.alloc();
    ge_const_flag(b, v, p, fl); // v <= p, so this is [v == p]
    for i in 0..v.len() {
        if p.bit(i) {
            b.cx(fl, v[i]);
        }
    }
    // fl = ctrl and [v == 0] now
    let z = b.alloc();
    ge_const_flag(b, v, U256::from(1u8), z);
    b.x(z);
    b.ccx(ctrl, z, fl);
    b.x(z);
    ge_const_flag(b, v, U256::from(1u8), z);
    b.release(z);
    b.release(fl);
}

/// acc <- acc - a (mod p).
pub fn mod_sub(b: &mut B, acc: &[QubitId], a: &[QubitId], p: U256) {
    super::builder::emit_inverse(b, |b| mod_add(b, acc, a, p));
}

/// z <- y^2 (mod p) for a zero register z (double-and-add over y's bits, most significant first).
pub fn mod_square_into(b: &mut B, y: &[QubitId], z: &[QubitId], p: U256) {
    b.label("mod_square");
    let n = y.len();
    let e = b.alloc();
    for i in (0..n).rev() {
        // z <- 2z (mod p): the inverse of halving
        super::builder::emit_inverse(b, |b| mod_halve(b, z, e, p));
        // z <- z + y_i * y (mod p); the mask's own bit i is y_i itself
        let m = b.alloc_n(n);
        for j in 0..n {
            if j == i {
                b.cx(y[i], m[j]);
            } else {
                b.ccx(y[i], y[j], m[j]);
            }
        }
        mod_add(b, z, &m, p);
        for j in 0..n {
            if j == i {
                b.cx(y[i], m[j]);
            } else {
                b.ccx(y[i], y[j], m[j]);
            }
        }
        b.release_n(&m);
    }
    b.release(e);
}
