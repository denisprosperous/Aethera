"""Geometry utilities (v10.2 — no coordinates, no projections).

This module is intentionally minimal. The platform stores NO coordinates
(no x/y/z, no lon/lat). Only raw scalar edge lengths between point IDs.

Mode A (user survey): The user supplies absolute distances directly.
  e.g., total station measurements, LIDAR point-to-point distances,
  tape measures. The user provides:
      point_A, point_B, distance_meters
  No coordinates.

Mode B (topology bootstrapping): Placeholder 1.0 for all edges. The
  solver (Agent 2) infers true lengths from global area closure by
  minimising:
      E = Σ_edges (l_e - l_true)² + λ (Σ_areas - Global_Total)²
"""

# Default placeholder edge length for Mode B (topology bootstrapping).
PLACEHOLDER_LENGTH = 1.0


def placeholder_length() -> float:
    """Return the Mode B placeholder edge length (1.0).

    The solver infers true lengths from global area closure.
    """
    return PLACEHOLDER_LENGTH


def validate_survey_distance(distance: float) -> float:
    """Validate a user-supplied Mode A survey distance.

    Must be a positive, finite number. Returns the distance if valid,
    raises ValueError otherwise.
    """
    if not isinstance(distance, (int, float)):
        raise ValueError(f"distance must be a number, got {type(distance)}")
    if distance != distance:  # NaN check
        raise ValueError("distance is NaN")
    if distance == float("inf") or distance == float("-inf"):
        raise ValueError("distance is infinite")
    if distance <= 0:
        raise ValueError(f"distance must be positive, got {distance}")
    return float(distance)


def parse_survey_csv(csv_text: str) -> list:
    """Parse a Mode A user-supplied survey CSV.

    Format:
        point_A, point_B, distance_meters
        point_A, point_C, distance_meters
        ...

    Returns a list of (source_label, target_label, distance_meters) tuples.
    """
    edges = []
    for lineno, line in enumerate(csv_text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 3:
            raise ValueError(f"line {lineno}: expected 3 columns (point_a, point_b, distance)")
        distance = float(cols[2])
        validate_survey_distance(distance)
        edges.append((cols[0], cols[1], distance))
    return edges
