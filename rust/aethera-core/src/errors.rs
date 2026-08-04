use thiserror::Error;

#[derive(Debug, Error)]
pub enum AetheraError {
    #[error("underconstrained: {0} nodes, {1} edges")]
    Underconstrained(usize, usize),
    #[error("disconnected graph: {0}")]
    Disconnected(String),
    #[error("solver did not converge in {0} iterations (residual = {1})")]
    NoConverge(usize, f64),
    #[error("invalid input: {0}")]
    InvalidInput(String),
}

pub type Result<T> = std::result::Result<T, AetheraError>;
