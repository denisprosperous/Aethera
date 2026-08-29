# AETHERA Backend Dockerfile
# Builds the Rust FFI + Python FastAPI backend.

FROM rust:1.97-slim AS rust-builder
WORKDIR /app/rust
# gmp-mpfr-sys builds vendored GMP/MPFR from source — needs m4, make, gcc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    m4 make gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*
COPY rust/ ./rust/
RUN cd rust && cargo build -p aethera-ffi --release

FROM python:3.12-slim
WORKDIR /app

# Install system deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgmp-dev libmpfr-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy Rust shared library.
COPY --from=rust-builder /app/rust/rust/target/release/libaethera_ffi.so /usr/local/lib/
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV AETHERA_FFI_PATH=/usr/local/lib/libaethera_ffi.so

# Copy Python code.
COPY python/ ./python/
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/python

EXPOSE 8000
CMD ["uvicorn", "aethera.api:app", "--host", "0.0.0.0", "--port", "8000"]
