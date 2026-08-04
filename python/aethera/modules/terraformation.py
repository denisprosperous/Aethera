"""Module 5F — Terraformation Simulator."""
from dataclasses import dataclass, field
from typing import Dict, List
from .hall_of_shame import Polygon

@dataclass
class VolumeTransfer:
    source: str
    target: str
    volume_km3: float

@dataclass
class CoastlineChange:
    nation: str
    area_change_km2: float
    habitable_area_km2_before: float
    habitable_area_km2_after: float
    note: str

@dataclass
class ReparationsReport:
    transfers: List[VolumeTransfer]
    coastline_changes: List[CoastlineChange]
    reparations_index: Dict[str, float]
    note: str

class TerraformationSimulator:
    def __init__(self, polys):
        self.polys = {p.name: p for p in polys}
    def simulate(self, transfers):
        changes = {n: 0.0 for n in self.polys}
        for t in transfers:
            avg_depth_km = 0.1  # AETHERA-GUARD: ALLOW DOCUMENTATION (assumed avg depth)
            ac = t.volume_km3 / avg_depth_km
            changes[t.source] = changes.get(t.source, 0.0) - ac
            changes[t.target] = changes.get(t.target, 0.0) + ac
        cc = []; ri = {}
        for name, delta in changes.items():
            poly = self.polys.get(name)
            if poly is None: continue
            before = poly.area_km2_true
            after = max(0.0, before + delta)
            cc.append(CoastlineChange(name, delta, before, after,
                f"{name}: {delta:+.0f} km² ({before:.0f} → {after:.0f})."))
            ri[name] = delta
        return ReparationsReport(transfers, cc, ri,
            f"Simulated {len(transfers)} transfers. Net: {sum(changes.values()):+.0f} km².")
