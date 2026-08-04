"""Module 5A — Transparency Comparator. No targeting — just chord vs claimed range."""
import math
from dataclasses import dataclass
from typing import Tuple

@dataclass
class RangeClaim:
    launch_name: str
    target_name: str
    launch_xyz: Tuple[float, float, float]
    target_xyz: Tuple[float, float, float]
    claimed_range_m: float

@dataclass
class ExaggerationCertificate:
    launch: str; target: str
    claimed_range_m: float
    geometric_chord_m: float
    ratio: float
    is_exaggerated: bool
    note: str

class TransparencyComparator:
    def __init__(self, exaggeration_threshold=1.01):
        self.threshold = exaggeration_threshold
    def chord_distance(self, a, b):
        return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))
    def evaluate(self, claim):
        chord = self.chord_distance(claim.launch_xyz, claim.target_xyz)
        if chord <= 0:
            return ExaggerationCertificate(claim.launch_name, claim.target_name,
                claim.claimed_range_m, chord, float("inf"), True, "Zero chord.")
        ratio = claim.claimed_range_m / chord
        is_ex = ratio > self.threshold
        note = (f"Claimed {claim.claimed_range_m:.0f}m vs chord {chord:.0f}m (ratio {ratio:.3f}). "
                f"{'Exaggerated' if is_ex else 'Consistent'}. Transparency tool, no targeting.")
        return ExaggerationCertificate(claim.launch_name, claim.target_name,
            claim.claimed_range_m, chord, ratio, is_ex, note)
    def evaluate_many(self, claims): return [self.evaluate(c) for c in claims]
