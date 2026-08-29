"""Module 5C — Anomaly Daemon (v6.0 civil-scientific)."""
from dataclasses import dataclass
from typing import List, Tuple
from ..agents.acif import AcifSnapshot

@dataclass
class AnomalyAlert:
    edge: Tuple[str, str]
    epochs: Tuple[float, float]
    delta_per_day_cm: float
    note: str

class AnomalyDaemon:
    def __init__(self, threshold_cm_per_day=1.0):
        self.threshold = threshold_cm_per_day
    def run(self, snapshots: List[AcifSnapshot]) -> List[AnomalyAlert]:
        if len(snapshots) < 2: return []
        alerts = []
        for i in range(len(snapshots) - 1):
            s0, s1 = snapshots[i], snapshots[i+1]
            dt = (s1.epoch - s0.epoch) / 86400.0
            if dt <= 0: continue
            map0 = {(a,b): d for a,b,d in s0.edge_lengths}
            map1 = {(a,b): d for a,b,d in s1.edge_lengths}
            deltas = []
            for (a,b), d1 in map1.items():
                d0 = map0.get((a,b)) or map0.get((b,a))
                if d0 is None: continue
                deltas.append((a, b, (d1 - d0) * 100.0))
            if not deltas: continue
            sum_abs = sum(abs(d) for _,_,d in deltas); n = len(deltas)
            for a, b, dc in deltas:
                pd = dc / dt
                if abs(pd) < self.threshold: continue
                loo = (sum_abs - abs(dc)) / max(n-1, 1)
                is_local = abs(dc) > 1e-9 if loo < 1e-12 else (abs(dc)/loo) > 2.0
                if not is_local: continue
                alerts.append(AnomalyAlert((a,b), (s0.epoch, s1.epoch), pd,
                    f"Edge {a}-{b} {pd:+.3} cm/day. Possible: groundwater, glacial, volcanic, geothermal."))
        return alerts
