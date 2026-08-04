# Reformed Modules — v6.0 Engineering Rationale

## Agent 7 — From "Armaments Architect" (v5.0, declined) to "Dynamics Module" (v6.0, reformed)

### v5.0 (declined)

The v5.0 Agent 7 was specified as computing ballistic missile trajectories
with launch azimuth, elevation, and impact point — weapons-delivery code.
This was declined for harm policy and because the physics was wrong
(curvature alone doesn't give dynamics; GR's `G` couples geometry to matter).

### v6.0 (reformed — implemented)

**Ethical hardening:** The platform explicitly forbids itself from
outputting tactical firing solutions. It outputs raw inertial geodesic
distances, time-of-flight in a user-defined force field, and strain
tensors. Tactical application is left to external, user-supplied physics
engines.

**Scientific hardening:** The false claim that "gravity emerges from 2D
surface curvature" is removed. The platform supports dual dynamics modes:
(a) purely inertial shortest-path geodesics on the derived spatial
manifold (for routing/navigation), and (b) test-particle simulation under
a user-supplied acceleration field. The gravitational constant `G` is
never hardcoded; it is a user-input variable (`μ = G·M`).

### API safeguards

```python
# Mode A: shortest path — accepts start + end, returns path length.
result = dynamics.shortest_path(graph, manifold, start="A", end="C")
# Does NOT return: azimuth, elevation, impact_point

# Mode B: particle simulation — accepts start + initial velocity +
# user-supplied force field, returns trajectory.
result = simulate_particle(
    start=(0.0, 0.0, 0.0),
    initial_velocity=(1.0, 0.0, 0.0),
    accel_fn=inverse_square_field(mu=1.0),  # user supplies μ, NOT G
    config=ForceFieldConfig(dt=0.01, t_max=10.0),
)
# Does NOT accept: target, target_coords
# Does NOT return: azimuth, elevation, impact_point
```

The platform does **forward simulation**, not **inverse targeting**.

## Module 5B — From "Forecaster" to "StrainVisualizer"

v5.0 overclaimed earthquake prediction. v6.0 renames to StrainVisualizer
with explicit disclaimer: "This is a strain visualization tool.
Prediction accuracy depends on user-provided rupture models."

## Module 5C — Civil-scientific reframing

v5.0 mentioned "defense agencies" and "nuclear tests". v6.0 removes all
defense references. Use cases: groundwater depletion, glacial isostatic
adjustment, volcanic magma shifts, geothermal activity.

## Build guard — From build-killing to warning-level

v5.0 halted the build on any finding. v6.0 defaults to warning mode
(exit 0); `--strict` flag enables error mode (exit 1) as opt-in.
