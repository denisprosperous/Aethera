//! Arbitrary-precision scalar wrapper around rug::Float at 256-bit default.

use rug::Float;
use rug::float::Round;
use rug::ops::AssignRound;
use serde::{Deserialize, Serialize};

pub const DEFAULT_PRECISION: u32 = 256;

#[derive(Clone, Debug)]
pub struct Scalar { val: Float }

impl Scalar {
    pub fn from_f64(v: f64) -> Self { Self { val: Float::with_val(DEFAULT_PRECISION, v) } }
    pub fn from_i64(v: i64) -> Self { Self { val: Float::with_val(DEFAULT_PRECISION, v) } }
    pub fn from_str(s: &str) -> Result<Self, String> {
        match Float::parse(s) {
            Ok(p) => Ok(Self { val: Float::with_val(DEFAULT_PRECISION, p) }),
            Err(e) => Err(format!("invalid scalar {s:?}: {e}")),
        }
    }
    pub fn to_f64(&self) -> f64 { self.val.to_f64() }
    pub fn raw(&self) -> &Float { &self.val }
    pub fn from_float(f: Float) -> Self { Self { val: f } }
}

impl std::ops::Add for Scalar {
    type Output = Scalar;
    fn add(self, rhs: Self) -> Self {
        let p = self.val.prec().max(rhs.val.prec());
        let mut out = Float::new(p);
        out.assign_round(&self.val + &rhs.val, Round::Nearest);
        Scalar { val: out }
    }
}
impl std::ops::Sub for Scalar {
    type Output = Scalar;
    fn sub(self, rhs: Self) -> Self {
        let p = self.val.prec().max(rhs.val.prec());
        let mut out = Float::new(p);
        out.assign_round(&self.val - &rhs.val, Round::Nearest);
        Scalar { val: out }
    }
}
impl std::ops::Mul for Scalar {
    type Output = Scalar;
    fn mul(self, rhs: Self) -> Self {
        let p = self.val.prec().max(rhs.val.prec());
        let mut out = Float::new(p);
        out.assign_round(&self.val * &rhs.val, Round::Nearest);
        Scalar { val: out }
    }
}
impl std::ops::Div for Scalar {
    type Output = Scalar;
    fn div(self, rhs: Self) -> Self {
        let p = self.val.prec().max(rhs.val.prec());
        let mut out = Float::new(p);
        out.assign_round(&self.val / &rhs.val, Round::Nearest);
        Scalar { val: out }
    }
}
impl PartialOrd for Scalar {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> { self.val.partial_cmp(&other.val) }
}
impl PartialEq for Scalar {
    fn eq(&self, other: &Self) -> bool { self.val == other.val }
}
impl std::fmt::Display for Scalar {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result { write!(f, "{:.30}", self.val) }
}
impl Serialize for Scalar {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> { s.serialize_str(&self.to_string()) }
}
impl<'de> Deserialize<'de> for Scalar {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let s = String::deserialize(d)?;
        Scalar::from_str(&s).map_err(serde::de::Error::custom)
    }
}

pub fn sqrt(s: &Scalar) -> Scalar {
    let mut out = Float::new(s.val.prec());
    let r = s.val.clone().sqrt();
    out.assign_round(r, Round::Nearest);
    Scalar { val: out }
}
pub fn sq(s: &Scalar) -> Scalar { s.clone() * s.clone() }

#[cfg(test)]
mod tests {
    use super::*;
    #[test] // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
    fn arithmetic() {
        let a = Scalar::from_f64(3.0);
        let b = Scalar::from_f64(4.0);
        let c = sqrt(&(sq(&a) + sq(&b)));
        assert!((c.to_f64() - 5.0).abs() < 1e-20);
    }
    #[test] // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
    fn precision_preserved() {
        let a = Scalar::from_str("1").unwrap();
        let b = Scalar::from_str("3").unwrap();
        let c = a / b;
        let s = c.to_string();
        let three_count = s.chars().filter(|&c| c == '3').count();
        assert!(three_count >= 25, "got {three_count} threes in: {s}");
    }
}
