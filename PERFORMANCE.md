# AETHERA Solver Performance

## Rust FFI vs Python Fallback

| Metric | Rust (.so) | Python (numpy) | Speedup |
|--------|-----------|----------------|---------|
| 500-edge graph, 100 iterations | 0.064s | 0.110s | **1.7x** |
| Stress (same result) | 0.2640 | 0.2640 | — |

## Test Configuration

- Graph: 100 nodes, 500 edges (random edge lengths 0.5-5.0)
- Solver: SMACOF, 100 iterations, tol=1e-6
- Rust: `libaethera_ffi.so` compiled with `cargo build --release` (opt-level=3, LTO=thin)
- Python: numpy + scipy SMACOF fallback
- Platform: Linux x86_64

## Notes

The 1.7x speedup is modest because the pure-Python SMACOF uses numpy
vectorisation, which is already quite fast. The Rust advantage grows
significantly for:

- Larger graphs (>1000 nodes): Rust's rayon parallelism kicks in.
- Arbitrary-precision arithmetic: Rust's `rug` (GMP) is far faster than
  Python's `mpmath`.
- Repeated solves: Rust has no GC overhead.

For the current 100-140 region graphs used in the distortion observatory,
both solvers complete in <100ms, so the difference is imperceptible.
The Rust FFI is primarily a scaling investment for future multi-thousand
node graphs.

## Library Path

The Python bridge (`rust_bridge.py`) searches for the shared library at:
1. `rust/target/release/libaethera_ffi.so` (relative to repo root)
2. `/usr/local/lib/libaethera_ffi.so`
3. `$AETHERA_FFI_PATH` environment variable

If not found, it falls back to the pure-Python SMACOF with a warning.
