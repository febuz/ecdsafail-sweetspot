//! Minimal circuit builder: qubit allocation with id reuse (the score counts the highest qubit id + 1),
//! the gate set of the harness, and `emit_inverse` for reversible blocks.
use crate::circuit::{BitId, Op, OperationType, QubitId, RegisterId};

pub struct B {
    pub ops: Vec<Op>,
    next_qubit: u64,
    next_bit: u64,
    next_register: u64,
    free: Vec<u64>,
    pub active: u32,
    pub peak: u32,
    /// (op index, label) markers for diagnostics
    pub labels: Vec<(usize, &'static str)>,
    /// per-op tag: 1 = CCX computing a temporary AND into a fresh |0> wire
    pub tags: Vec<u8>,
}

impl B {
    pub fn new() -> Self {
        Self { ops: Vec::new(), next_qubit: 0, next_bit: 0, next_register: 0, free: Vec::new(), active: 0, peak: 0, labels: Vec::new(), tags: Vec::new() }
    }
    pub fn label(&mut self, l: &'static str) {
        self.labels.push((self.ops.len(), l));
    }
    pub fn alloc(&mut self) -> QubitId {
        self.active += 1;
        self.peak = self.peak.max(self.active);
        // lowest free id first keeps the highest referenced id at the live peak
        if let Some(pos) = (0..self.free.len()).min_by_key(|&i| self.free[i]) {
            QubitId(self.free.swap_remove(pos))
        } else {
            self.next_qubit += 1;
            QubitId(self.next_qubit - 1)
        }
    }
    /// Allocate a specific free qubit id (used to put outputs back on their input wires).
    pub fn alloc_id(&mut self, id: QubitId) -> QubitId {
        let pos = self.free.iter().position(|&q| q == id.0).expect("alloc_id: qubit is not free");
        self.free.swap_remove(pos);
        self.active += 1;
        self.peak = self.peak.max(self.active);
        id
    }
    pub fn is_free(&self, id: QubitId) -> bool {
        self.free.contains(&id.0)
    }
    pub fn alloc_n(&mut self, n: usize) -> Vec<QubitId> {
        (0..n).map(|_| self.alloc()).collect()
    }
    pub fn alloc_bit(&mut self) -> BitId {
        self.next_bit += 1;
        BitId(self.next_bit - 1)
    }
    pub fn alloc_bits(&mut self, n: usize) -> Vec<BitId> {
        (0..n).map(|_| self.alloc_bit()).collect()
    }
    /// Release a qubit that the circuit has returned to |0> (the R checks it in simulation via the phase).
    pub fn release(&mut self, q: QubitId) {
        self.op(OperationType::R, None, None, Some(q), None);
        self.free.push(q.0);
        self.active -= 1;
    }
    pub fn release_n(&mut self, qs: &[QubitId]) {
        for &q in qs {
            self.release(q);
        }
    }
    fn op(&mut self, kind: OperationType, c2: Option<QubitId>, c1: Option<QubitId>, t: Option<QubitId>, cond: Option<BitId>) {
        let mut o = Op::empty();
        o.kind = kind;
        if let Some(q) = c2 { o.q_control2 = q; }
        if let Some(q) = c1 { o.q_control1 = q; }
        if let Some(q) = t { o.q_target = q; }
        if let Some(c) = cond { o.c_condition = c; }
        self.ops.push(o);
        self.tags.push(0);
    }
    pub fn x(&mut self, t: QubitId) { self.op(OperationType::X, None, None, Some(t), None); }
    pub fn x_if(&mut self, t: QubitId, c: BitId) { self.op(OperationType::X, None, None, Some(t), Some(c)); }
    pub fn cx(&mut self, c: QubitId, t: QubitId) { self.op(OperationType::CX, None, Some(c), Some(t), None); }
    pub fn cx_if(&mut self, c: QubitId, t: QubitId, cond: BitId) { self.op(OperationType::CX, None, Some(c), Some(t), Some(cond)); }
    pub fn ccx(&mut self, a: QubitId, b: QubitId, t: QubitId) { self.op(OperationType::CCX, Some(a), Some(b), Some(t), None); }
    pub fn cz_if(&mut self, a: QubitId, b: QubitId, cond: BitId) { self.op(OperationType::CZ, None, Some(a), Some(b), Some(cond)); }
    pub fn hmr(&mut self, q: QubitId, m: BitId) {
        let mut o = Op::empty();
        o.kind = OperationType::Hmr;
        o.q_target = q;
        o.c_target = m;
        self.ops.push(o);
        self.tags.push(0);
    }
    /// Temporary logical AND (Gidney 2018): t <- a & b on a fresh |0> wire (1 Toffoli).
    pub fn and_compute(&mut self, a: QubitId, b: QubitId, t: QubitId) {
        self.ccx(a, b, t);
        *self.tags.last_mut().unwrap() = 1;
    }
    /// Erase t = a & b by an X-basis measurement and a classically controlled CZ (0 Toffoli); t ends in |0>.
    pub fn and_uncompute(&mut self, a: QubitId, b: QubitId, t: QubitId) {
        let m = self.alloc_bit();
        self.hmr(t, m);
        self.cz_if(a, b, m);
    }
    pub fn swap(&mut self, a: QubitId, b: QubitId) { self.op(OperationType::Swap, None, Some(a), Some(b), None); }
    /// Fredkin: swap a and b when c (1 Toffoli).
    pub fn cswap(&mut self, c: QubitId, a: QubitId, b: QubitId) {
        self.cx(b, a);
        self.ccx(c, a, b);
        self.cx(b, a);
    }
    pub fn declare_qubit_register(&mut self, qs: &[QubitId]) {
        let r = RegisterId(self.next_register);
        self.next_register += 1;
        for &q in qs {
            let mut o = Op::empty();
            o.kind = OperationType::AppendToRegister;
            o.q_target = q;
            o.r_target = r;
            self.ops.push(o);
            self.tags.push(0);
        }
        let mut o = Op::empty();
        o.kind = OperationType::Register;
        o.r_target = r;
        self.ops.push(o);
        self.tags.push(0);
    }
    pub fn declare_bit_register(&mut self, bs: &[BitId]) {
        let r = RegisterId(self.next_register);
        self.next_register += 1;
        for &b in bs {
            let mut o = Op::empty();
            o.kind = OperationType::AppendToRegister;
            o.c_target = b;
            o.r_target = r;
            self.ops.push(o);
            self.tags.push(0);
        }
        let mut o = Op::empty();
        o.kind = OperationType::Register;
        o.r_target = r;
        self.ops.push(o);
        self.tags.push(0);
    }
}

/// Run `f`, then replace its ops by their reverse (a reversible block; its releases are dropped, so every qubit it
/// allocated must be |0> again at its release point, which the reverse restores). Temporary ANDs swap roles: an
/// X-measurement erase (HMR + conditional CZ) becomes a Toffoli compute, and a tagged Toffoli compute becomes an
/// X-measurement erase, so the reverse costs the same Toffoli count as the forward.
pub fn emit_inverse<F: FnOnce(&mut B)>(b: &mut B, f: F) {
    let start = b.ops.len();
    f(b);
    let fwd: Vec<Op> = b.ops.drain(start..).collect();
    let tags: Vec<u8> = b.tags.drain(start..).collect();
    let mut k = fwd.len();
    while k > 0 {
        k -= 1;
        let o = fwd[k];
        match o.kind {
            OperationType::CZ if o.c_condition != crate::circuit::NO_BIT => {
                // paired with the HMR just before it: reverse of an AND erase is its compute
                let h = fwd[k - 1];
                assert!(h.kind == OperationType::Hmr && h.c_target == o.c_condition, "emit_inverse: unpaired conditional CZ");
                b.ccx(o.q_control1, o.q_target, h.q_target);
                *b.tags.last_mut().unwrap() = 1;
                k -= 1;
            }
            OperationType::CCX if tags[k] == 1 => {
                b.and_uncompute(o.q_control2, o.q_control1, o.q_target);
            }
            OperationType::X | OperationType::Z | OperationType::CX | OperationType::CZ | OperationType::CCX
            | OperationType::CCZ | OperationType::Swap => {
                b.ops.push(o);
                b.tags.push(0);
            }
            OperationType::R => {}
            kind => panic!("emit_inverse: non-invertible op {kind:?}"),
        }
    }
}
