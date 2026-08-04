"""Module 5D — Maritime Chokepoint Reconstructor."""
import math
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Chokepoint:
    name: str
    width_m: float
    depth_m: float
    draft_m: float
    beam_m: float

@dataclass
class NavigabilityReport:
    name: str
    tide_offset_m: float
    effective_width_m: float
    effective_depth_m: float
    navigable: bool
    max_vessel_beam_m: float
    max_vessel_draft_m: float
    navigability_index: float
    note: str

class MaritimeChokepoint:
    def __init__(self, safety_margin_m=50.0):
        self.safety = safety_margin_m
    def evaluate(self, cp, tide_offset_m=0.0):
        ed = cp.depth_m + tide_offset_m
        ew = cp.width_m
        md = ed - self.safety
        mb = ew
        nav = md >= cp.draft_m and mb >= cp.beam_m
        di = min(1.0, max(0.0, md / max(cp.draft_m, 1e-12))) * min(1.0, mb / max(cp.beam_m, 1e-12))
        note = f"{cp.name}: tide {tide_offset_m:+.2f}m, eff depth {ed:.2f}m. {'Navigable' if nav else 'NOT navigable'}."
        return NavigabilityReport(cp.name, tide_offset_m, ew, ed, nav, mb, md, di, note)
    def evaluate_over_tide_range(self, cp, tide_range):
        return [self.evaluate(cp, t) for t in tide_range]
    def shortest_transit_path(self, chokes, tide_offset_m):
        nav = [c for c in chokes if self.evaluate(c, tide_offset_m).navigable]
        if not nav: return ([], 0.0)
        return ([c.name for c in nav], sum(c.width_m for c in nav))
