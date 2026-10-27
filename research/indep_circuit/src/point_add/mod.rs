//! Independent point add (DivPay), built from textbook parts:
//!   x <- x - ox, y <- y - oy                      (dx, dy)
//!   y <- y / x                                    (lambda; divsteps division, x kept)
//!   x <- x + 3 ox - y^2                           (= ox - x3)
//!   y <- y * x                                    (the division run backwards: lambda (ox - x3) = y3 + oy)
//!   y <- y - oy, x <- ox - x                      (y3, x3)
mod arith;
mod builder;
pub mod divide;
mod rail_w;
mod square;

use crate::circuit::Op;
use alloy_primitives::U256;
use arith::*;
use builder::{emit_inverse, B};

pub const N: usize = 256;
pub const P: U256 = U256::from_limbs([0xFFFFFFFEFFFFFC2F, u64::MAX, u64::MAX, u64::MAX]);
/// Half-delta divsteps steps. Proven bound 591 (sipa); 0 of 1.2M random inputs needed more than 537.
pub const STEPS: usize = 540;

pub fn build() -> Vec<Op> {
    let b = &mut B::new();
    let x = b.alloc_n(N);
    b.declare_qubit_register(&x);
    let y = b.alloc_n(N);
    b.declare_qubit_register(&y);
    let ox = b.alloc_bits(N);
    b.declare_bit_register(&ox);
    let oy = b.alloc_bits(N);
    b.declare_bit_register(&oy);
    point_add(b, &x, &y, &ox, &oy, STEPS);
    std::mem::take(&mut b.ops)
}

pub fn point_add(b: &mut B, x: &[crate::circuit::QubitId], y: &[crate::circuit::QubitId], ox: &[crate::circuit::BitId], oy: &[crate::circuit::BitId], steps: usize) {
    let t = load_bits(b, ox);
    mod_sub(b, x, &t, P);
    unload_bits(b, &t, ox);
    let t = load_bits(b, oy);
    mod_sub(b, y, &t, P);
    unload_bits(b, &t, oy);

    divide::divide(b, y, x, P, steps);

    let t = load_bits(b, ox);
    for _ in 0..3 {
        mod_add(b, x, &t, P);
    }
    unload_bits(b, &t, ox);
    square::mod_sub_square(b, x, y, P);

    emit_inverse(b, |b| divide::divide(b, y, x, P, steps));

    let t = load_bits(b, oy);
    mod_sub(b, y, &t, P);
    unload_bits(b, &t, oy);
    let one = b.alloc();
    b.x(one);
    cmod_neg_safe(b, x, one, P);
    b.x(one);
    b.release(one);
    let t = load_bits(b, ox);
    mod_add(b, x, &t, P);
    unload_bits(b, &t, ox);
}
