#!/usr/bin/env python3
"""AETHERA — ETOPO1 global DEM downloader (v25.0).

Downloads ETOPO1 Ice Surface (1 arc-minute, GMT4 NetCDF) from NOAA NCEI
with streaming + retries, verifies the gzip integrity and decompresses.

Usage:
    python scripts/download_etopo1.py [--data-dir data] [--retries 3]
"""

import argparse
import gzip
import sys
import time
from pathlib import Path

import requests

ETOPO1_URL = (
    "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO1/data/ice_surface/"
    "grid_registered/netcdf/ETOPO1_Ice_g_gmt4.grd.gz"
)
GZ_NAME = "ETOPO1_Ice_g_gmt4.grd.gz"
NC_NAME = "ETOPO1_Ice_g_gmt4.grd.nc"

# Minimum plausible size for the real ETOPO1 grid (bytes).
MIN_GZ_BYTES = 100_000_000  # ~380 MB expected; anything smaller is truncated


def download(data_dir: Path, retries: int = 3) -> Path:
    gz_path = data_dir / GZ_NAME
    nc_path = data_dir / NC_NAME

    if nc_path.exists() and nc_path.stat().st_size > MIN_GZ_BYTES:
        print(f"[download] already present: {nc_path}")
        return nc_path

    data_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            print(f"[download] attempt {attempt}/{retries}: {ETOPO1_URL}")
            with requests.get(ETOPO1_URL, stream=True, timeout=(30, 300)) as r:
                r.raise_for_status()
                total = 0
                with open(gz_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            fh.write(chunk)
                            total += len(chunk)
                            if total % (50 << 20) < (1 << 20):
                                print(f"[download]   {total / 1e6:7.0f} MB")
            if total < MIN_GZ_BYTES:
                raise RuntimeError(f"truncated download: {total} bytes")
            print(f"[download] got {total/1e6:.0f} MB, verifying gzip...")
            with gzip.open(gz_path, "rb") as fh:
                while fh.read(1 << 24):
                    pass  # full CRC check
            print("[download] gzip OK, decompressing...")
            with gzip.open(gz_path, "rb") as fin, open(nc_path, "wb") as fout:
                while True:
                    block = fin.read(1 << 24)
                    if not block:
                        break
                    fout.write(block)
            gz_path.unlink(missing_ok=True)
            print(f"[download] done: {nc_path} ({nc_path.stat().st_size/1e6:.0f} MB)")
            return nc_path
        except Exception as e:  # noqa: BLE001
            print(f"[download] attempt {attempt} failed: {e}", file=sys.stderr)
            gz_path.unlink(missing_ok=True)
            if attempt < retries:
                wait = 15 * attempt
                print(f"[download] retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
    raise RuntimeError("ETOPO1 download failed after all retries")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()
    download(Path(args.data_dir), args.retries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
