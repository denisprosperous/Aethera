"""Module 5E — Consensus Hall of Shame. Projection strain tensor + Colonial Distortion Score."""
import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

def mercator(lon, lat):
    lr = math.radians(max(-89.999, min(89.999, lat)))
    return (math.radians(lon), math.log(math.tan(math.pi/4 + lr/2)))
def robinson(lon, lat):
    lr = math.radians(lat)
    return (math.radians(lon) * math.cos(lr * 0.7), lr * (1.0 - 0.1 * lr**2))
def authagraph(lon, lat):
    lr = math.radians(lat)
    return (math.radians(lon) * math.cos(lr), math.sin(lr))
def equirectangular(lon, lat):
    return (math.radians(lon), math.radians(lat))

PROJECTIONS = {"Mercator": mercator, "Robinson": robinson,
    "AuthaGraph": authagraph, "Equirectangular": equirectangular}

@dataclass
class Polygon:
    name: str
    vertices_lonlat: List[Tuple[float, float]]
    area_km2_true: float
    coloniser: bool = False

@dataclass
class StrainField:
    polygon_name: str
    centroid: Tuple[float, float]
    area_projected: float
    area_true: float
    scale_factor: float
    log_strain: float
    colour: Tuple[float, float, float]

@dataclass
class DistortionScore:
    projection: str
    mean_log_strain: float
    std_log_strain: float
    max_inflation: float
    max_deflation: float
    colonial_distortion_score: float
    note: str

def _shoelace(v):
    if len(v) < 3: return 0.0
    s = 0.0
    for i in range(len(v)):
        x1, y1 = v[i]; x2, y2 = v[(i+1) % len(v)]
        s += x1*y2 - x2*y1
    return abs(s) / 2.0

def _centroid(v):
    n = len(v)
    return (sum(p[0] for p in v)/n, sum(p[1] for p in v)/n)

def strain_field(polys, proj, name):
    out = []
    for p in polys:
        verts = [proj(lon, lat) for lon, lat in p.vertices_lonlat]
        ap = _shoelace(verts)
        scale = ap / max(p.area_km2_true, 1e-12)
        ls = math.log(max(scale, 1e-12))
        cent = _centroid(verts)
        if ls > 0:
            t = min(1.0, ls / 2.0); col = (1.0, 1.0-t, 1.0-t)
        else:
            t = min(1.0, -ls / 2.0); col = (1.0-t, 1.0-t, 1.0)
        out.append(StrainField(p.name, cent, ap, p.area_km2_true, scale, ls, col))
    return out

def colonial_distortion_score(polys, proj, name):
    sfs = strain_field(polys, proj, name)
    cs = [s.log_strain for s, p in zip(sfs, polys) if p.coloniser]
    ds = [s.log_strain for s, p in zip(sfs, polys) if not p.coloniser]
    mc = sum(cs) / max(len(cs), 1); md = sum(ds) / max(len(ds), 1)
    alls = [s.log_strain for s in sfs]
    ma = sum(alls) / max(len(alls), 1)
    std = math.sqrt(sum((x-ma)**2 for x in alls) / max(len(alls), 1)) if alls else 0.0
    score = mc - md
    return DistortionScore(name, ma, std,
        max(alls) if alls else 0.0, min(alls) if alls else 0.0, score,
        f"{name}: coloniser mean {mc:+.3f}, colonised mean {md:+.3f}. Score {score:+.3f}.")

class HallOfShame:
    def __init__(self, polys): self.polys = polys
    def all_scores(self):
        return [colonial_distortion_score(self.polys, p, n) for n, p in PROJECTIONS.items()]
