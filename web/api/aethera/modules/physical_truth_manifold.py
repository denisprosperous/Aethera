"""Physical Truth manifold builder (v10.6).

Bridges the Physical Truth data (from compare_ingestion.py) to the
Intrinsic Geometer (Agent 2). Builds an EdgeGraph from the Physical
Truth regions, solves it with SMACOF, and returns the intrinsic
manifold coordinates.

The edge lengths are derived from the physical areas of adjacent
regions — NOT from lon/lat coordinates. Two regions that share a
boundary get an edge whose length is proportional to the square root
of the smaller region's area (a scale proxy).

This produces a manifold where:
- Each region is a node.
- Edges connect adjacent regions.
- The solver reconstructs the intrinsic layout purely from area-derived
  edge lengths + global area closure.

No lon/lat, no coordinates, no projections — pure Tabula Rasa.
"""

import math
import sys
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from aethera.core import EdgeGraph, Scalar, IntrinsicManifold
from aethera.agents.geometer import IntrinsicGeometer
from aethera.modules.compare_ingestion import REGIONS_PHYSICAL_TRUTH


# ---- Adjacency definitions -------------------------------------------
# Which regions share a boundary (land neighbours) or are adjacent
# (ocean basins). These are topological facts, NOT coordinates.
REGION_ADJACENCIES = [
    # Continental adjacencies
    ("Africa", "Europe"),
    ("Africa", "Asia"),
    ("Europe", "Asia"),
    ("North America", "South America"),
    ("Asia", "Oceania"),
    ("Antarctica", "South America"),
    ("Antarctica", "Africa"),
    ("Antarctica", "Oceania"),
    # Sub-region adjacencies within continents
    ("Russia", "China"),
    ("Russia", "Europe"),
    ("Russia", "Asia"),
    ("China", "India"),
    ("China", "Russia"),
    ("India", "Asia"),
    ("Brazil", "South America"),
    ("Brazil", "Argentina"),
    ("United States", "Canada"),
    ("United States", "North America"),
    ("Canada", "North America"),
    ("Canada", "United States"),
    ("Argentina", "South America"),
    ("Argentina", "Brazil"),
    ("Kazakhstan", "Russia"),
    ("Kazakhstan", "China"),
    ("Algeria", "Africa"),
    ("Algeria", "Libya"),
    ("DR Congo", "Africa"),
    ("Saudi Arabia", "Asia"),
    ("Mexico", "North America"),
    ("Mexico", "United States"),
    ("Indonesia", "Oceania"),
    ("Iran", "Asia"),
    ("Iran", "Saudi Arabia"),
    ("Mongolia", "Russia"),
    ("Mongolia", "China"),
    ("Peru", "South America"),
    ("Peru", "Brazil"),
    ("Chad", "Africa"),
    ("Chad", "Libya"),
    ("Niger", "Africa"),
    ("Niger", "Chad"),
    ("Angola", "Africa"),
    ("Mali", "Africa"),
    ("South Africa", "Africa"),
    ("Colombia", "South America"),
    ("Colombia", "Brazil"),
    ("Ethiopia", "Africa"),
    ("Bolivia", "South America"),
    ("Bolivia", "Brazil"),
    ("Egypt", "Africa"),
    ("Egypt", "Libya"),
    ("Tanzania", "Africa"),
    ("Nigeria", "Africa"),
    ("Venezuela", "South America"),
    ("Pakistan", "Asia"),
    ("Pakistan", "India"),
    ("Pakistan", "China"),
    ("Namibia", "Africa"),
    ("Mozambique", "Africa"),
    ("Turkey", "Europe"),
    ("Turkey", "Asia"),
    ("Chile", "South America"),
    ("Chile", "Argentina"),
    ("Zambia", "Africa"),
    ("Myanmar", "Asia"),
    ("France", "Europe"),
    ("Somalia", "Africa"),
    ("Afghanistan", "Asia"),
    ("South Sudan", "Africa"),
    ("Madagascar", "Africa"),
    ("Botswana", "Africa"),
    ("Kenya", "Africa"),
    ("Yemen", "Asia"),
    ("Thailand", "Asia"),
    ("Spain", "Europe"),
    ("Spain", "France"),
    ("Turkmenistan", "Asia"),
    ("Cameroon", "Africa"),
    ("Papua New Guinea", "Oceania"),
    ("Sweden", "Europe"),
    ("Uzbekistan", "Asia"),
    ("Morocco", "Africa"),
    ("Morocco", "Algeria"),
    ("Iraq", "Asia"),
    ("Iraq", "Saudi Arabia"),
    ("Iraq", "Iran"),
    ("Paraguay", "South America"),
    ("Zimbabwe", "Africa"),
    ("Japan", "Asia"),
    ("Germany", "Europe"),
    ("Germany", "France"),
    ("Republic of the Congo", "Africa"),
    ("Finland", "Europe"),
    ("Vietnam", "Asia"),
    ("Malaysia", "Asia"),
    ("Norway", "Europe"),
    ("Norway", "Sweden"),
    ("Ivory Coast", "Africa"),
    ("Poland", "Europe"),
    ("Poland", "Germany"),
    ("Oman", "Asia"),
    ("Oman", "Saudi Arabia"),
    ("Italy", "Europe"),
    ("Philippines", "Asia"),
    ("Ecuador", "South America"),
    ("Burkina Faso", "Africa"),
    ("New Zealand", "Oceania"),
    ("Gabon", "Africa"),
    ("Guinea", "Africa"),
    ("United Kingdom", "Europe"),
    ("Ghana", "Africa"),
    ("Romania", "Europe"),
    ("Laos", "Asia"),
    ("Uganda", "Africa"),
    ("Guyana", "South America"),
    ("Belarus", "Europe"),
    ("Kyrgyzstan", "Asia"),
    ("Senegal", "Africa"),
    ("Syria", "Asia"),
    ("Cambodia", "Asia"),
    ("Uruguay", "South America"),
    ("Suriname", "South America"),
    ("Tunisia", "Africa"),
    ("Tunisia", "Algeria"),
    ("Bangladesh", "Asia"),
    ("Bangladesh", "India"),
    ("Nepal", "Asia"),
    ("Nepal", "India"),
    ("Nepal", "China"),
    ("Tajikistan", "Asia"),
    ("Greece", "Europe"),
    ("Nicaragua", "North America"),
    ("North Korea", "Asia"),
    ("Malawi", "Africa"),
    ("Eritrea", "Africa"),
    ("Benin", "Africa"),
    ("Honduras", "North America"),
    ("Liberia", "Africa"),
    ("Bulgaria", "Europe"),
    ("Cuba", "North America"),
    ("Guatemala", "North America"),
    ("Iceland", "Europe"),
    ("South Korea", "Asia"),
    ("Hungary", "Europe"),
    ("Portugal", "Europe"),
    ("Portugal", "Spain"),
    ("Jordan", "Asia"),
    ("Serbia", "Europe"),
    ("Azerbaijan", "Asia"),
    ("Austria", "Europe"),
    ("United Arab Emirates", "Asia"),
    ("Czech Republic", "Europe"),
    ("Panama", "North America"),
    ("Sierra Leone", "Africa"),
    ("Ireland", "Europe"),
    ("Georgia", "Asia"),
    ("Sri Lanka", "Asia"),
    ("Lithuania", "Europe"),
    ("Latvia", "Europe"),
    ("Togo", "Africa"),
    ("Croatia", "Europe"),
    ("Bosnia and Herzegovina", "Europe"),
    ("Costa Rica", "North America"),
    ("Slovakia", "Europe"),
    ("Estonia", "Europe"),
    ("Denmark", "Europe"),
    ("Netherlands", "Europe"),
    ("Switzerland", "Europe"),
    ("Bhutan", "Asia"),
    ("Taiwan", "Asia"),
    ("Albania", "Europe"),
    ("Equatorial Guinea", "Africa"),
    ("Burundi", "Africa"),
    ("Haiti", "North America"),
    ("Rwanda", "Africa"),
    ("Moldova", "Europe"),
    ("Belgium", "Europe"),
    ("Armenia", "Asia"),
    ("Solomon Islands", "Oceania"),
    ("Israel", "Asia"),
]


def build_physical_truth_edge_graph() -> Tuple[EdgeGraph, Dict[str, float]]:
    """Build an EdgeGraph from Physical Truth data.

    Edge lengths are derived from the physical areas of adjacent regions.
    For two adjacent regions A and B, the edge length is:
        l = sqrt(min(area_A, area_B))

    This is a scale proxy — the solver will reconstruct positions
    purely from these area-derived lengths + global area closure.

    Returns (graph, area_map) where area_map is {region_name: area_km2}.
    """
    # Build area lookup.
    area_map = {}
    for entry in REGIONS_PHYSICAL_TRUTH:
        name, verts, area_true, coloniser = entry
        area_map[name] = area_true

    # Build edge graph from adjacencies.
    graph = EdgeGraph()
    for a, b in REGION_ADJACENCIES:
        if a in area_map and b in area_map:
            # Edge length = sqrt of the smaller area (scale proxy).
            length = math.sqrt(min(area_map[a], area_map[b]))
            graph.add_edge(a, b, Scalar(length), source="physical_truth")

    return graph, area_map


def solve_physical_truth_manifold(max_iter: int = 500, tol: float = 1e-10) -> Tuple[IntrinsicManifold, Dict[str, float]]:
    """Solve the Physical Truth manifold.

    Returns (manifold, area_map) where manifold.coords contains the
    intrinsic coordinates of each region.
    """
    graph, area_map = build_physical_truth_edge_graph()
    geo = IntrinsicGeometer(max_iter=max_iter, tol=tol)
    mf = geo.solve_2d(graph)
    return mf, area_map


def get_region_area(region_name: str) -> Optional[float]:
    """Get the physical area of a region (km²)."""
    for entry in REGIONS_PHYSICAL_TRUTH:
        name, verts, area_true, coloniser = entry
        if name == region_name:
            return area_true
    return None


def list_regions() -> List[Dict]:
    """List all Physical Truth regions with their areas."""
    return [
        {"name": name, "area_km2": area_true, "coloniser": coloniser}
        for name, verts, area_true, coloniser in REGIONS_PHYSICAL_TRUTH
    ]
