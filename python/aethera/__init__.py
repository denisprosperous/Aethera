"""AETHERA — first objective geometric substrate."""
__version__ = "0.2.0"
try:
    from . import _rust  # type: ignore
    HAS_RUST = True
except ImportError:
    HAS_RUST = False
from .core import EdgeGraph, Scalar, IntrinsicManifold, Point3
from .agents import (
    GhostResolver, IntrinsicGeometer, AcifNavigator, AlienGeometer, DynamicsModule,
)
from .modules import (
    TransparencyComparator, StrainVisualizer, AnomalyDaemon,
    MaritimeChokepoint, HallOfShame, TerraformationSimulator, StellarPositioning,
)
__all__ = [
    "EdgeGraph", "Scalar", "IntrinsicManifold", "Point3",
    "GhostResolver", "IntrinsicGeometer", "AcifNavigator", "AlienGeometer",
    "DynamicsModule",
    "TransparencyComparator", "StrainVisualizer", "AnomalyDaemon",
    "MaritimeChokepoint", "HallOfShame", "TerraformationSimulator",
    "StellarPositioning", "HAS_RUST",
]
