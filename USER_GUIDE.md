# AETHERA User Guide

Welcome to AETHERA — the world's first sovereign, unbiased computational geometry platform.

---

## Quick Start

### Access the Platform

1. **Local Development:**
   - Backend: http://localhost:8765
   - Frontend: http://localhost:3000/dashboard

2. **Production (when deployed):**
   - Backend: https://aethera-backend.up.railway.app
   - Frontend: https://aethera.vercel.app

---

## Dashboard Overview

The dashboard shows 9 module cards. Click any card to explore the module.

### Modules

| Module | Purpose | Icon |
|--------|---------|------|
| Ghost Resolver | Derive unknown areas from topology | 🔮 |
| Distortion Observatory | Compare projections to truth | 📊 |
| Consensus Hall | View Colonial Distortion Scores | 🏛️ |
| Terraformer | Simulate sea-level rise | 🌊 |
| Anomaly Detector | Detect edge-length drifts | ⚡ |
| Physical Truth | Reconstruct global manifold | 🌍 |
| Alien Geometer | Reconstruct shapes from edges | 👽 |
| Celestial Dynamics | Simulate particle motion | 🪐 |
| Terraformation | Simulate terraforming scenarios | 🌿 |

---

## Using the Ghost Resolver

The Ghost Resolver derives areas of missing/censored regions using topological residual closure.

### Step 1: Navigate to Module

Click "Ghost Resolver" on the dashboard.

### Step 2: Understand the Input

The module requires:
- **Polygons**: List of regions with known areas and neighbors
- **Global Enclosure**: Name of the containing region (e.g., "World")
- **Global Area**: Total area constraint

### Step 3: Run the Test

Click "Execute" to run the default test case.

**Example Test:**
```json
{
  "polygons": [
    {"name": "A", "area": 100, "neighbours": ["B", "C"]},
    {"name": "B", "area": 200, "neighbours": ["A", "C"]},
    {"name": "C", "area": null, "neighbours": ["A", "B"]}
  ],
  "global_enclosure": "World",
  "global_area": 500
}
```

### Step 4: Interpret Results

The response includes:
- **resolved_areas**: Derived areas for each polygon
- **red_flags**: Regions with >5% deviation from claimed area
- **rationale_log**: Plain English explanation with confidence
- **sealed_hash**: Cryptographic proof of computation

---

## Using the Distortion Observatory

Compare any map projection against AETHERA's absolute truth.

### Step 1: Navigate to Module

Click "Distortion Observatory" on the dashboard.

### Step 2: View Scores

The module shows Colonial Distortion Scores for:
- Mercator
- Robinson
- AuthaGraph
- Equirectangular

### Step 3: Interpret Results

**Colonial Distortion Score:**
- Negative = Colonizer lands inflated, colonized lands deflated
- Positive = Colonizer lands deflated, colonized lands inflated
- Zero = Fair representation

**Example:**
- Mercator: -0.84 (severely favors Europe)
- AuthaGraph: +0.37 (better balance)

---

## Using the Terraformer

Simulate sea-level rise impact on coastlines.

### Step 1: Navigate to Module

Click "Terraformer" on the dashboard.

### Step 2: Set Parameters

Enter sea-level rise in meters (e.g., 10 for 10m rise).

### Step 3: Run Simulation

Click "Execute" to simulate.

### Step 4: Interpret Results

The response shows:
- **coastline_changes**: Per-nation area loss/gain
- **total_land_loss**: Total area lost to sea
- **note**: Explanation of the model used

---

## Using the Physical Truth Manifold

Reconstruct the intrinsic geometry of Earth from raw edge lengths.

### Step 1: Navigate to Module

Click "Physical Truth" on the dashboard.

### Step 2: View Results

The module shows:
- 140 regions embedded in 2D intrinsic space
- Each region's coordinates emerge from edge lengths only
- No lat/lon, no projection, no coordinate system assumed

### Step 3: Export Data

Click "Export" to download the manifold as JSON.

---

## Using the Alien Geometer

Reconstruct shapes from raw edge measurements.

### Step 1: Navigate to Module

Click "Alien Geometer" on the dashboard.

### Step 2: Input Edges

Provide edge measurements between points.

**Example:**
```json
{
  "edges": [
    {"source": "A", "target": "B", "length": 100},
    {"source": "B", "target": "C", "length": 100},
    {"source": "C", "target": "A", "length": 100}
  ]
}
```

### Step 3: Run Reconstruction

Click "Execute" to reconstruct the shape.

### Step 4: Interpret Results

The response classifies the shape:
- **Flat**: Planar geometry
- **Ellipsoidal**: Positive curvature
- **Potato**: Irregular topology

---

## Using Celestial Dynamics

Simulate particle motion under user-defined force fields.

### Step 1: Navigate to Module

Click "Celestial Dynamics" on the dashboard.

### Step 2: Set Parameters

- **start**: Initial position [x, y, z]
- **initial_velocity**: Starting velocity [vx, vy, vz]
- **force_law**: "inertial", "uniform", or "inverse_square"
- **dt**: Time step
- **t_max**: Total simulation time

### Step 3: Run Simulation

Click "Execute" to simulate.

### Step 4: View Trajectory

The response includes:
- **trajectory**: List of [x, y, z] positions over time
- **total_path_length**: Cumulative distance traveled
- **final_position**: Where the particle ends up

---

## Uploading Survey Data

Upload CSV files with user-supplied edge measurements.

### CSV Format

```csv
point_A,point_B,distance_meters
A,B,100.5
B,C,150.2
C,A,120.8
```

### Upload Steps

1. Navigate to any module
2. Click "Upload Survey"
3. Select your CSV file
4. Click "Solve" to reconstruct the manifold

---

## Understanding Rationale Logs

Every computation includes a Rationale Engine log explaining:

1. **What was computed**: Plain English description
2. **Confidence**: Percentage certainty (0-100%)
3. **Adjacency**: Which regions interact
4. **Sealing**: Cryptographic hash for verification

### Example Rationale

```
"Derived via Topological Residual Closure. Confidence: 99.99%. 
 Adjacency: [B, C]. Seal: sha256:abc123..."
```

---

## Tips & Best Practices

1. **Start with Ghost Resolver** — simplest module, great for testing
2. **Check Distortion Observatory** — see how projections bias representation
3. **Use Terraformer** — understand climate change impact
4. **Export Physical Truth** — get the absolute geometric substrate
5. **Verify with Rationale** — always check the confidence scores

---

## Troubleshooting

### Frontend won't load
- Check backend is running: `http://localhost:8765/api/health`
- Clear browser cache
- Try incognito mode

### API returns 500 error
- Check backend logs in terminal
- Verify request body format
- Check database connection

### Slow responses
- First request warms up the solver
- Subsequent requests are faster
- Consider compiling Rust engine for 10x speedup

---

## Next Steps

1. Explore all 9 modules
2. Upload your own survey data
3. Deploy to production (see DEPLOYMENT_GUIDE.md)
4. Contribute to the project on GitHub

---

**AETHERA is built for transparency, accuracy, and sovereignty. Use it wisely.**
