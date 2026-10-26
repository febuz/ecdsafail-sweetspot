//! Tail sampler for the leader's active walk (lever A, `a2_rails.rs`, 122 ticks).
//!
//! The walk is a port of the leader's own reference model `a2_ref::walk_t0` (which the leader's
//! `a2_walk_tests` check against the circuit's tape letters). Per tick it records the signed width each
//! value needs and compares it with the fitted table `a2_R122_steps.txt` (W n0 n1 n2 nb):
//!   W  <- rails at tick start,  n0/n1 <- forced sums before halving,  n2 <- the taken choice sum,
//!   nb <- the barrel input (choice sum / 2).
//! Tick 0's choice is a circuit predicate the model does not reproduce; `--t0 both` walks both
//! admissible options and keeps the worse (conservative).
//!
//! Usage: lf_tail <samples> <seed> [--t0 ref|both]   (prints a JSON summary)
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

#[derive(Clone, Copy, PartialEq, Debug)]
struct I5([u64; 5]);
impl I5 {
    fn add(&self, b: &I5) -> I5 { let mut r = [0u64; 5]; let mut c = false; for i in 0..5 { let (x, c1) = self.0[i].overflowing_add(b.0[i]); let (y, c2) = x.overflowing_add(c as u64); r[i] = y; c = c1 || c2; } I5(r) }
    fn sub(&self, b: &I5) -> I5 { let mut r = [0u64; 5]; let mut c = false; for i in 0..5 { let (x, c1) = self.0[i].overflowing_sub(b.0[i]); let (y, c2) = x.overflowing_sub(c as u64); r[i] = y; c = c1 || c2; } I5(r) }
    fn neg_p(&self) -> bool { self.0[4] >> 63 == 1 }
    fn is_zero(&self) -> bool { self.0.iter().all(|&w| w == 0) }
    fn sar(&self, k: u32) -> I5 { if k == 0 { return *self; } let mut r = [0u64; 5]; for i in 0..4 { r[i] = (self.0[i] >> k) | (self.0[i + 1] << (64 - k)); } r[4] = ((self.0[4] as i64) >> k) as u64; I5(r) }
    fn bit(&self, i: usize) -> bool { self.0[i / 64] >> (i % 64) & 1 == 1 }
    fn ctz(&self) -> usize { for i in 0..5 { if self.0[i] != 0 { return 64 * i + self.0[i].trailing_zeros() as usize; } } 99 }
    fn winv(&self, h: usize, l: usize) -> u128 {
        let m = if self.neg_p() { u64::MAX } else { 0 };
        let mut v: u128 = 0;
        for j in 0..l { let p = h + j; if p < 320 && ((self.0[p / 64] ^ m) >> (p % 64)) & 1 == 1 { v |= 1 << j; } }
        v
    }
    /// Minimal two's complement width.
    fn width(&self) -> usize {
        let m = if self.neg_p() { u64::MAX } else { 0 };
        for i in (0..5).rev() { let w = self.0[i] ^ m; if w != 0 { return 64 * i + 64 - w.leading_zeros() as usize + 1; } }
        1
    }
    fn abs(&self) -> I5 { if self.neg_p() { I5([0; 5]).sub(self) } else { *self } }
    fn gt(&self, b: &I5) -> bool { for i in (0..5).rev() { if self.0[i] != b.0[i] { return self.0[i] > b.0[i]; } } false }
    /// [`winv`] that saturates to all ones when the magnitude has bits above the window.
    fn winv_sat(&self, h: usize, l: usize) -> u128 {
        let m = if self.neg_p() { u64::MAX } else { 0 };
        for p in h + l..319 { if ((self.0[p / 64] ^ m) >> (p % 64)) & 1 == 1 { return (1u128 << l) - 1; } }
        self.winv(h, l)
    }
    fn is_pm1(&self) -> bool { *self == I5([1, 0, 0, 0, 0]) || *self == I5([u64::MAX; 5]) }
}
fn p() -> I5 { I5([0xFFFF_FFFE_FFFF_FC2F, u64::MAX, u64::MAX, u64::MAX, 0]) }

fn lwin(t: usize) -> usize {
    let sch: &[(usize, usize)] = &[(0, 22), (1, 13), (4, 17), (9, 22), (81, 19), (91, 17), (102, 15), (107, 13), (113, 11)];
    sch.iter().filter(|&&(f, _)| t >= f).last().unwrap().1
}

const COLS: usize = 5;
/// need - table per tick and column, for one walk.
type Need = Vec<[i32; COLS]>;

/// The walk with tick 0's deep/flat forced (`t0deep`); None if that option is not admissible.
fn slack() -> [i32; COLS] {
    // LF_SLACK=a,b,c,d,e: bits each column may exceed the table by without failing (default 0)
    let mut s = [0; COLS];
    if let Ok(v) = std::env::var("LF_SLACK") { for (i, x) in v.split(',').enumerate() { s[i] = x.parse().unwrap(); } }
    s
}

fn walk(d: &I5, anch: &[usize], tab: &[[usize; 5]], t0deep: Option<bool>) -> Option<(Need, bool)> {
    let sl = slack();
    let r = tab.len();
    let pp = p();
    let r0 = if d.0[0] & 1 == 1 { *d } else { d.sub(&pp) };
    let x = if r0.bit(1) { r0.add(&pp) } else { r0.sub(&pp) };
    let mut rr = [r0, x.sar(1)];
    let fam = |m: u32| -> bool { let r0 = m & 0x15; let r1 = m & 0x2a; r0.count_ones() <= 1 && r1.count_ones() <= 1 };
    let mut pfx: u32 = 0;
    let mut cnt = [0usize; 2];
    let mut need = Vec::with_capacity(r);
    for t in 0..r {
        let tw = tab[t];
        let a = t & 1;
        let last = t == r - 1;
        let nf = if last { 0 } else { 2 };
        let b = rr[1 - a];
        let mut tk = rr[a];
        let mut row = [i32::MIN; COLS];
        row[0] = tk.width().max(b.width()) as i32 - tw[0] as i32 - sl[0];
        let (mut added, mut flipped) = (false, false);
        let bn = b.neg_p();
        for i in 0..nf {
            let s = tk.bit(1) == b.bit(1);
            let xx = if s { tk.add(&b) } else { tk.sub(&b) };
            row[1 + i] = xx.width() as i32 - tw[1 + i] as i32 - sl[1 + i];
            let tn = tk.neg_p();
            let ad = tn == (bn ^ !s);
            let tnew = xx.sar(1);
            let fl = !ad && tnew.neg_p() != tn;
            if i == nf - 1 { added = ad; flipped = fl; }
            tk = tnew;
        }
        let sd = tk.bit(1) != b.bit(1);
        let (xd, xf) = if sd { (tk.add(&b), tk.sub(&b)) } else { (tk.sub(&b), tk.add(&b)) };
        let z = xd.is_zero();
        let v = if z { 99 } else { xd.ctz() };
        let e_eq = !z && (tk.neg_p() == (bn ^ !sd));
        if t % 6 == 0 { pfx = 0; }
        let mut cap = if t == 0 || last { 3 } else { emax() };
        let (m, k) = grp();
        let (j, a2) = (t / 2, t & 1);
        if m > 0 && j % m == 0 { cnt[a2] = 0; }
        if m > 0 && cap > 3 && cnt[a2] >= k { cap = 3; }
        if m == 0 && cap > 3 && famon() && !fam(pfx | 1 << (t % 6)) { cap = 3; }
        let l = lwin(t) + envc("LF_LADD", 0);
        let h = (anch[t.min(anch.len() - 1)] + envc("LF_HUP", 0)).saturating_sub(l - 2);
        let (wa, wb) = match rule() {
            // exact: encode the comparison so that wa > (wb << 1) <=> |T| > 2|B| (and << 2 for the last tick)
            1 => { let (x, y) = (tk.abs(), b.abs()); let big = if last { x.gt(&y.add(&y).add(&y.add(&y))) } else { x.gt(&y.add(&y)) }; (big as u128, 0) }
            2 => (tk.winv_sat(h, l), b.winv_sat(h, l)),
            _ => (tk.winv(h, l), b.winv(h, l)),
        };
        let mut deep = false;
        if v <= cap + 1 {
            deep = if last {
                if !(e_eq && v == 2) { true } else { wa > (wb << 2) }
            } else if t == 0 {
                !(e_eq && v == 2)
            } else if !e_eq {
                true
            } else {
                match v { 2 => wa > (wb << 1) || flipped, 3 => wa > (wb << 1) || !added, _ => true }
            };
        }
        if t == 0 {
            if let Some(g) = t0deep {
                if g && v > cap + 1 { return None; }
                deep = g;
            }
        }
        if deep && v - 1 >= 4 { pfx |= 1 << (t % 6); cnt[a2] += 1; }
        let taken = if deep { xd } else { xf };
        row[3] = taken.width() as i32 - tw[3] as i32 - sl[3];
        row[4] = taken.sar(1).width() as i32 - tw[4] as i32 - sl[4];
        rr[a] = if deep { xd.sar(v as u32) } else { xf.sar(1) };
        need.push(row);
    }
    Some((need, rr[0].is_pm1() && rr[1].is_pm1()))
}

/// Exact walk without widths, run up to `max` ticks with no special last tick (anchors clamped to the
/// table's last entry): the number of ticks after which both rails are first +-1 (`max` if never).
fn park_tick(d: &I5, anch: &[usize], max: usize) -> usize {
    let pp = p();
    let r0 = if d.0[0] & 1 == 1 { *d } else { d.sub(&pp) };
    let x = if r0.bit(1) { r0.add(&pp) } else { r0.sub(&pp) };
    let mut rr = [r0, x.sar(1)];
    let fam = |m: u32| -> bool { let r0 = m & 0x15; let r1 = m & 0x2a; r0.count_ones() <= 1 && r1.count_ones() <= 1 };
    let mut pfx: u32 = 0;
    let mut cnt = [0usize; 2];
    for t in 0..max {
        let a = t & 1;
        let b = rr[1 - a];
        let mut tk = rr[a];
        let (mut added, mut flipped) = (false, false);
        let bn = b.neg_p();
        for i in 0..2 {
            let s = tk.bit(1) == b.bit(1);
            let xx = if s { tk.add(&b) } else { tk.sub(&b) };
            let tn = tk.neg_p();
            let ad = tn == (bn ^ !s);
            let tnew = xx.sar(1);
            let fl = !ad && tnew.neg_p() != tn;
            if i == 1 { added = ad; flipped = fl; }
            tk = tnew;
        }
        let sd = tk.bit(1) != b.bit(1);
        let (xd, xf) = if sd { (tk.add(&b), tk.sub(&b)) } else { (tk.sub(&b), tk.add(&b)) };
        let z = xd.is_zero();
        let v = if z { 99 } else { xd.ctz() };
        let e_eq = !z && (tk.neg_p() == (bn ^ !sd));
        if t % 6 == 0 { pfx = 0; }
        let mut cap = if t == 0 { 3 } else { emax() };
        if cap > 7 && t % envc("LF_E8EVERY", 1).max(1) != envc("LF_E8OFF", 0) { cap = 7; }
        let (m, k) = grp();
        let (j, a2) = (t / 2, t & 1);
        if m > 0 && j % m == 0 { cnt[a2] = 0; }
        if m > 0 && cap > 3 && cnt[a2] >= k { cap = 3; }
        if m == 0 && cap > 3 && famon() && !fam(pfx | 1 << (t % 6)) { cap = 3; }
        let l = lwin(t) + envc("LF_LADD", 0);
        let h = (anch[t.min(anch.len() - 1)] + envc("LF_HUP", 0)).saturating_sub(l - 2);
        let big = match rule() {
            1 => tk.abs().gt(&b.abs().add(&b.abs())),
            2 => tk.winv_sat(h, l) > (b.winv_sat(h, l) << 1),
            _ => tk.winv(h, l) > (b.winv(h, l) << 1),
        };
        let mut deep = false;
        if v <= cap + 1 {
            deep = if t == 0 { !(e_eq && v == 2) } else if !e_eq { true } else {
                match v { 2 => big || flipped, 3 => big || !added, _ => true }
            };
        }
        if deep && v - 1 >= 4 { pfx |= 1 << (t % 6); cnt[a2] += 1; }
        rr[a] = if deep { xd.sar(v as u32) } else { xf.sar(1) };
        if rr[0].is_pm1() && rr[1].is_pm1() { return t + 1; }
    }
    max
}

fn envu(k: &str, d: usize) -> usize { std::env::var(k).ok().and_then(|v| v.parse().ok()).unwrap_or(d) }
/// park_tick variants: LF_RULE 0 = leader windows, 1 = exact |T| > 2|B|, 2 = saturating windows;
/// LF_EMAX digit cap (7); LF_FAM 0 drops the one-e>=4-per-triple record constraint.
fn rule() -> usize { static V: std::sync::OnceLock<usize> = std::sync::OnceLock::new(); *V.get_or_init(|| envu("LF_RULE", 0)) }
fn emax() -> usize { static V: std::sync::OnceLock<usize> = std::sync::OnceLock::new(); *V.get_or_init(|| envu("LF_EMAX", 7)) }
/// LF_M, LF_K: at most k e>=4 events per block of m same-rail ticks (m = 0: the leader's triples)
fn grp() -> (usize, usize) { static V: std::sync::OnceLock<(usize, usize)> = std::sync::OnceLock::new(); *V.get_or_init(|| (envu("LF_M", 0), envu("LF_K", 1))) }
fn envc(k: &'static str, d: usize) -> usize {
    static V: std::sync::OnceLock<std::collections::HashMap<&'static str, usize>> = std::sync::OnceLock::new();
    *V.get_or_init(|| ["LF_LADD", "LF_HUP", "LF_E8EVERY", "LF_E8OFF"].iter().map(|&k| (k, envu(k, 0))).collect()).get(k).unwrap_or(&d)
}
fn recmin() -> i32 { static V: std::sync::OnceLock<i32> = std::sync::OnceLock::new(); *V.get_or_init(|| std::env::var("LF_RECMIN").ok().and_then(|v| v.parse().ok()).unwrap_or(1)) }
fn famon() -> bool { static V: std::sync::OnceLock<usize> = std::sync::OnceLock::new(); *V.get_or_init(|| envu("LF_FAM", 1)) == 1 }

fn splitmix(s: &mut u64) -> u64 { *s = s.wrapping_add(0x9E37_79B9_7F4A_7C15); let mut z = *s; z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9); z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB); z ^ (z >> 31) }
fn rnd_d(s: &mut u64) -> I5 {
    let pp = p();
    loop {
        let v = I5([splitmix(s), splitmix(s), splitmix(s), splitmix(s), 0]);
        if !v.is_zero() && v.sub(&pp).neg_p() { return v; }
    }
}

const LO: i32 = -6; // histogram of need - table over [LO, HI]
const HI: i32 = 6;
const NB: usize = (HI - LO + 1) as usize;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n: u64 = args[1].parse().unwrap();
    let seed: u64 = args[2].parse().unwrap();
    let both = args.iter().any(|a| a == "both");
    let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let tab: Vec<[usize; 5]> = std::fs::read_to_string(std::env::var("LF_TABLE").map(std::path::PathBuf::from).unwrap_or(dir.join("a2_R122_steps.txt"))).unwrap().lines()
        .filter(|l| !l.trim().is_empty() && !l.starts_with('#'))
        .map(|l| { let v: Vec<usize> = l.split_whitespace().map(|x| x.parse().unwrap()).collect(); [v[0], v[1], v[2], v[3], v[4]] })
        .collect();
    let anch: Vec<usize> = std::fs::read_to_string(dir.join("a2_R122_anch.txt")).unwrap().split(',').filter_map(|v| v.trim().parse().ok()).collect();
    let r = tab.len();
    if args.iter().any(|a| a == "--stdin") {
        // one hex d per line -> worst excess (column, tick) for both tick-0 options, parked, park tick
        for line in std::io::stdin().lines() {
            let line = line.unwrap();
            let h = line.trim().trim_start_matches("0x");
            if h.is_empty() { continue; }
            let h = format!("{:0>64}", h);
            let mut l = [0u64; 5];
            for i in 0..4 { l[3 - i] = u64::from_str_radix(&h[16 * i..16 * i + 16], 16).unwrap(); }
            let d = I5(l);
            let mut out = Vec::new();
            for g in [None, Some(true), Some(false)] {
                match walk(&d, &anch, &tab, g) {
                    None => out.push("inadmissible".to_string()),
                    Some((need, pk)) => {
                        let mut best = (i32::MIN, 0, 0);
                        for (t, row) in need.iter().enumerate() { for c in 0..COLS { if row[c] > best.0 { best = (row[c], t, c); } } }
                        let first = need.iter().position(|row| row.iter().any(|&v| v != i32::MIN && v >= 1));
                        out.push(format!("max_excess={} at t{} col{} first_over={:?} parked={}", best.0, best.1, best.2, first, pk));
                    }
                }
            }
            println!("{} | ref: {} | t0deep: {} | t0flat: {} | park_tick={}", h, out[0], out[1], out[2], park_tick(&d, &anch, 200));
        }
        return;
    }
    if args.iter().any(|a| a == "--park") {
        // park tick histogram only (no widths): the tail a rule variant leaves
        let threads = std::thread::available_parallelism().map(|v| v.get()).unwrap_or(4) as u64;
        let ptk: Arc<Vec<AtomicU64>> = Arc::new((0..=200).map(|_| AtomicU64::new(0)).collect());
        let hs: Vec<_> = (0..threads).map(|th| { let (anch, ptk) = (anch.clone(), ptk.clone()); std::thread::spawn(move || {
            let mut s = seed.wrapping_mul(0x1000_0000_01B3) ^ th.wrapping_mul(0xA24B_AED4_963E_E407);
            for _ in 0..n / threads + u64::from(th < n % threads) { ptk[park_tick(&rnd_d(&mut s), &anch, 200)].fetch_add(1, Ordering::Relaxed); }
        }) }).collect();
        for h in hs { h.join().unwrap(); }
        let v: Vec<u64> = (0..=200).map(|i| ptk[i].load(Ordering::Relaxed)).collect();
        let mean = v.iter().enumerate().map(|(i, &c)| i as f64 * c as f64).sum::<f64>() / n as f64;
        let tail = |k: usize| v[k + 1..].iter().sum::<u64>();
        println!("rule {} emax {} fam {} m,k {:?} n {n}: mean {mean:.3} | >110 {} >116 {} >120 {} >122 {} >125 {} >128 {} >131 {} | max {}", rule(), emax(), famon() as u8, grp(),
            tail(110), tail(116), tail(120), tail(122), tail(125), tail(128), tail(131), v.iter().rposition(|&c| c > 0).unwrap());
        // ticks R needed so that P(park > R) <= rate
        let need = |rate: f64| (0..=200).find(|&k| (tail(k) as f64) <= rate * n as f64).unwrap();
        println!("  R needed: 1e-4 {} | 1e-5 {} | 1e-6 {}", need(1e-4), need(1e-5), need(1e-6));
        return;
    }
    let threads = std::thread::available_parallelism().map(|v| v.get()).unwrap_or(4) as u64;
    // shared: histogram [tick][col][bin], walks with any excess >= k for k = 1, 2, 3, not parked
    let hist: Arc<Vec<AtomicU64>> = Arc::new((0..r * COLS * NB).map(|_| AtomicU64::new(0)).collect());
    let over: Arc<Vec<AtomicU64>> = Arc::new((0..5).map(|_| AtomicU64::new(0)).collect());
    let rec_path = std::env::var("LF_RECORDS").unwrap_or_else(|_| "/dev/null".into());
    let rec = Arc::new(std::sync::Mutex::new(std::io::BufWriter::new(std::fs::File::create(rec_path).unwrap())));
    let ptk: Arc<Vec<AtomicU64>> = Arc::new((0..=200).map(|_| AtomicU64::new(0)).collect());
    let tmax: Arc<Vec<AtomicU64>> = Arc::new((0..r * 72).map(|_| AtomicU64::new(0)).collect());
    let worst: Arc<Vec<AtomicU64>> = Arc::new((0..r * COLS).map(|_| AtomicU64::new(0)).collect());
    let mut hs = Vec::new();
    for th in 0..threads {
        let (tab, anch, hist, over, worst, ptk, rec, tmax) = (tab.clone(), anch.clone(), hist.clone(), over.clone(), worst.clone(), ptk.clone(), rec.clone(), tmax.clone());
        hs.push(std::thread::spawn(move || {
            let mut s = seed.wrapping_mul(0x1000_0000_01B3) ^ th.wrapping_mul(0xA24B_AED4_963E_E407);
            let per = n / threads + u64::from(th < n % threads);
            for _ in 0..per {
                let d = rnd_d(&mut s);
                let opts: Vec<(Need, bool)> = if both {
                    [Some(true), Some(false)].iter().filter_map(|&g| walk(&d, &anch, &tab, g)).collect()
                } else {
                    vec![walk(&d, &anch, &tab, None).unwrap()]
                };
                // worst over the tick-0 options, per tick and column
                let mut need = opts[0].0.clone();
                let mut parked = opts[0].1;
                for (o, pk) in &opts[1..] {
                    parked &= *pk;
                    for (row, orow) in need.iter_mut().zip(o) { for c in 0..COLS { row[c] = row[c].max(orow[c]); } }
                }
                let mut mx = i32::MIN;
                for (t, row) in need.iter().enumerate() {
                    let m = row.iter().copied().filter(|&v| v != i32::MIN).max().unwrap();
                    tmax[t * 72 + (m.clamp(-63, 8) + 63) as usize].fetch_add(1, Ordering::Relaxed);
                    for c in 0..COLS {
                        if row[c] == i32::MIN { continue; }
                        mx = mx.max(row[c]);
                        let bin = (row[c].clamp(LO, HI) - LO) as usize;
                        hist[(t * COLS + c) * NB + bin].fetch_add(1, Ordering::Relaxed);
                        worst[t * COLS + c].fetch_max((row[c] + 1000) as u64, Ordering::Relaxed);
                    }
                }
                for k in 1..=3 { if mx >= k { over[k as usize - 1].fetch_add(1, Ordering::Relaxed); } }
                if !parked { over[3].fetch_add(1, Ordering::Relaxed); }
                let pt = park_tick(&d, &anch, 200);
                if !parked || mx >= 1 { over[4].fetch_add(1, Ordering::Relaxed); }
                // LF_RECMIN (default 1): also record walks within reach of a narrower refit table
                if !parked || mx >= recmin() {
                    // failing walk record: park tick, then the worst excess per tick (over columns and t0 options)
                    let ex: Vec<String> = need.iter().map(|row| row.iter().filter(|&&v| v != i32::MIN).copied().max().unwrap().max(-9).to_string()).collect();
                    let line = format!("{} {}\n", pt, ex.join(","));
                    use std::io::Write;
                    rec.lock().unwrap().write_all(line.as_bytes()).unwrap();
                }
                ptk[pt.min(200)].fetch_add(1, Ordering::Relaxed);
            }
        }));
    }
    for h in hs { h.join().unwrap(); }
    { use std::io::Write; rec.lock().unwrap().flush().unwrap(); }
    let get = |v: &AtomicU64| v.load(Ordering::Relaxed);
    let mut ticks = Vec::new();
    for t in 0..r {
        let mut cols = Vec::new();
        for c in 0..COLS {
            let hv: Vec<String> = (0..NB).map(|b| get(&hist[(t * COLS + c) * NB + b]).to_string()).collect();
            let w = get(&worst[t * COLS + c]);
            let w = if w == 0 { "null".to_string() } else { (w as i64 - 1000).to_string() };
            cols.push(format!("{{\"worst\":{w},\"hist\":[{}]}}", hv.join(",")));
        }
        ticks.push(format!("[{}]", cols.join(",")));
    }
    println!("{{\"samples\":{n},\"seed\":{seed},\"t0\":\"{}\",\"bins_from\":{LO},\"walks_excess_ge\":[{},{},{}],\"not_parked\":{},\"fail_union\":{},\"park_tick_hist\":[{}],\"tmax_from\":-63,\"tmax\":[{}],\"ticks\":[{}]}}",
        if both { "both" } else { "ref" }, get(&over[0]), get(&over[1]), get(&over[2]), get(&over[3]), get(&over[4]), (0..=200).map(|i| get(&ptk[i]).to_string()).collect::<Vec<_>>().join(","),
        (0..r).map(|t| format!("[{}]", (0..72).map(|b| get(&tmax[t * 72 + b]).to_string()).collect::<Vec<_>>().join(","))).collect::<Vec<_>>().join(","), ticks.join(","));
}
