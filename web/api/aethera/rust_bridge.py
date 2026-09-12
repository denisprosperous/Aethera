"""Rust FFI bridge — calls the compiled AETHERA solver via ctypes.

Falls back to the pure-Python SMACOF if the shared library is not available.
"""

import os
import ctypes
import json
from typing import List, Tuple, Optional, Dict
from pathlib import Path

# Try to find the shared library.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATHS = [
    # Relative to repo root: rust/target/release/
    _REPO_ROOT / "rust" / "target" / "release" / "libaethera_ffi.so",
    _REPO_ROOT / "rust" / "target" / "release" / "aethera_ffi.dll",
    _REPO_ROOT / "rust" / "target" / "release" / "libaethera_ffi.dylib",
    # System paths.
    Path("/usr/local/lib/libaethera_ffi.so"),
    Path("/usr/lib/libaethera_ffi.so"),
    # Environment variable override.
    Path(os.environ.get("AETHERA_FFI_PATH", "/nonexistent")),
]

_rust_lib = None
_USE_RUST = False

for _path in _LIB_PATHS:
    if _path.exists():
        try:
            _rust_lib = ctypes.CDLL(str(_path))
            _USE_RUST = True
            # Configure function signatures.
            class CEdge(ctypes.Structure):
                _fields_ = [
                    ("source", ctypes.c_char_p),
                    ("target", ctypes.c_char_p),
                    ("length", ctypes.c_double),
                ]

            class CCoord(ctypes.Structure):
                _fields_ = [
                    ("name", ctypes.c_char_p),
                    ("x", ctypes.c_double),
                    ("y", ctypes.c_double),
                ]

            class CSolveResult(ctypes.Structure):
                _fields_ = [
                    ("coords", ctypes.POINTER(CCoord)),
                    ("count", ctypes.c_int),
                    ("stress", ctypes.c_double),
                ]

            _rust_lib.aethera_solve_2d.argtypes = [
                ctypes.POINTER(CEdge), ctypes.c_int, ctypes.c_int, ctypes.c_double,
            ]
            _rust_lib.aethera_solve_2d.restype = CSolveResult
            _rust_lib.aethera_free_result.argtypes = [ctypes.POINTER(CSolveResult)]
            _rust_lib.aethera_free_result.restype = None

            _CEdge = CEdge
            _CCoord = CCoord
            _CSolveResult = CSolveResult
            break
        except Exception as e:
            print(f"[aethera] Failed to load Rust library from {_path}: {e}")
            _rust_lib = None


def is_rust_available() -> bool:
    """Returns True if the Rust shared library is loaded."""
    return _USE_RUST


def solve_manifold_rust(edges: List[Tuple[str, str, float]],
                          max_iter: int = 500, tol: float = 1e-10) -> Optional[Dict]:
    """Solve a 2D manifold using the Rust SMACOF solver.

    Args:
        edges: List of (source, target, length) tuples.
        max_iter: Maximum SMACOF iterations.
        tol: Convergence tolerance.

    Returns:
        Dict with 'coordinates' (dict of name -> [x, y]) and 'stress' (float),
        or None if the Rust library is not available.
    """
    if not _USE_RUST:
        return None

    # Build C edge array.
    c_edges = (_CEdge * len(edges))()
    for i, (source, target, length) in enumerate(edges):
        c_edges[i].source = source.encode("utf-8")
        c_edges[i].target = target.encode("utf-8")
        c_edges[i].length = length

    # Call Rust.
    result = _rust_lib.aethera_solve_2d(
        c_edges, len(edges), max_iter, tol,
    )

    if result.count == 0:
        return None

    # Extract coordinates.
    coords = {}
    for i in range(result.count):
        coord = result.coords[i]
        name = coord.name.decode("utf-8") if coord.name else f"node_{i}"
        coords[name] = [coord.x, coord.y]

    stress = result.stress

    # Free Rust memory.
    _rust_lib.aethera_free_result(ctypes.byref(result))

    return {"coordinates": coords, "stress": stress}


def solve_manifold(edges: List[Tuple[str, str, float]],
                    max_iter: int = 500, tol: float = 1e-10) -> Dict:
    """Solve a 2D manifold — uses Rust if available, falls back to Python.

    Args:
        edges: List of (source, target, length) tuples.

    Returns:
        Dict with 'coordinates', 'stress', 'solver' ('rust' or 'python').
    """
    # Try Rust first.
    if _USE_RUST:
        result = solve_manifold_rust(edges, max_iter, tol)
        if result is not None:
            result["solver"] = "rust"
            return result

    # Fallback to Python.
    from aethera.core import EdgeGraph, Scalar
    from aethera.agents.geometer import IntrinsicGeometer

    graph = EdgeGraph()
    for source, target, length in edges:
        graph.add_edge(source, target, Scalar(length))

    geo = IntrinsicGeometer(max_iter=max_iter, tol=tol)
    mf = geo.solve_2d(graph)
    coords = {name: [p.x, p.y] for name, p in mf.coords.items()}
    return {"coordinates": coords, "stress": mf.residual, "solver": "python"}
