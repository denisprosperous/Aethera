# AETHERA API Reference

Base URL: `http://localhost:8765/api` (local) or `https://aethera-backend.up.railway.app/api` (production)

---

## Health Check

### GET /health

Returns platform status.

**Response:**
```json
{
  "status": "ok",
  "version": "0.3.0",
  "database": "connected",
  "solver": "python_fallback",
  "llm": {
    "primary": "GLM-5.2 (Z.ai VibeSDK)",
    "any_available": true
  }
}
```

---

## Ghost Resolver

### POST /ghost/resolve

Derive unknown polygon areas via topological residual closure.

**Request:**
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

**Response:**
```json
{
  "resolved_areas": {"A": 100.0, "B": 200.0, "C": 200.0},
  "red_flags": [],
  "rationale_log": [
    {"polygon": "A", "confidence_pct": 99.99, "rationale": "Derived via Topological Residual Closure..."}
  ],
  "sealed_hash": "sha256:...",
  "note": "Areas derived via topological residual closure."
}
```

---

## Physical Truth Manifold

### GET /solve/physical-truth

Reconstruct the global manifold from area-derived edge lengths.

**Response:**
```json
{
  "regions": [
    {"name": "Africa", "coords": [2494.4, -861.7, 0.0], "area_km2": 30370000},
    {"name": "Europe", "coords": [-668.7, -444.3, 0.0], "area_km2": 10180000}
  ],
  "node_count": 140,
  "edge_count": 174,
  "residual": 0.0001
}
```

---

## Distortion Observatory

### GET /projections/scores

Compute Colonial Distortion Scores for scholarly projections.

**Response:**
```json
{
  "scores": [
    {
      "projection": "Mercator",
      "colonial_score": -0.8377,
      "max_inflation": -12.28,
      "max_deflation": -16.73,
      "note": "Mercator: coloniser mean -16.008, colonised mean -15.171."
    }
  ]
}
```

### GET /distortion/global

Get global distortion index for all projections.

### GET /distortion/region/{region_name}

Get distortion metrics for a specific region.

### GET /distortion/ranking?projection=Mercator&order=desc&limit=20

Get regions ranked by distortion magnitude.

---

## Terraformation

### POST /terraformation

Simulate sea-level rise impact.

**Request:**
```json
{
  "sea_level_rise_m": 10
}
```

**Response:**
```json
{
  "sea_level_rise_m": 10.0,
  "coastline_changes": [
    {
      "nation": "Greenland",
      "area_change_km2": -36100000.0,
      "before": 2166086,
      "after": 0.0
    }
  ],
  "note": "Simplified volumetric model."
}
```

---

## Alien Geometer

### POST /alien/reconstruct

Reconstruct intrinsic shape from raw edge lengths.

**Request:**
```json
{
  "edges": [
    {"source": "A", "target": "B", "length": 1.0, "source_type": "topology"},
    {"source": "B", "target": "C", "length": 1.0, "source_type": "topology"},
    {"source": "C", "target": "A", "length": 1.0, "source_type": "topology"}
  ]
}
```

**Response:**
```json
{
  "shape": "Flat",
  "embedding": "2D",
  "residual": 2.7e-16,
  "mean_curvature": 0.0,
  "node_count": 3,
  "edge_count": 3
}
```

---

## Celestial Dynamics

### POST /dynamics/simulate

Simulate particle trajectory under force field.

**Request:**
```json
{
  "start": [0, 0, 0],
  "initial_velocity": [1, 0, 0],
  "force_law": "uniform",
  "uniform_accel": [0, 0, -9.81],
  "dt": 0.1,
  "t_max": 5.0
}
```

**Response:**
```json
{
  "trajectory": [[0, 0, 0], [0.1, 0, 0], ...],
  "total_path_length": 5.0,
  "total_time": 5.0,
  "final_position": [4.999, 0, -122.6],
  "note": "Uniform field [0, 0, -9.81]. Targeting solutions NOT provided."
}
```

---

## Data Inventory

### GET /datasets

List all ingested regions.

**Response:**
```json
{
  "regions": [
    {"region": "Africa", "status": "done", "edge_count": 2251, "face_count": 54},
    {"region": "Europe", "status": "done", "edge_count": 1500, "face_count": 32}
  ]
}
```

### GET /regions/{region}/edges

Get raw edges for a region.

---

## Anomaly Detector

### GET /anomaly/latest

Get latest anomaly alerts.

**Response:**
```json
{
  "alerts": [],
  "note": "No anomalies detected."
}
```

---

## LLM Interface

### GET /llm/status

Check LLM provider status.

**Response:**
```json
{
  "primary": "GLM-5.2 (Z.ai VibeSDK)",
  "configured": true,
  "fallback_chain": ["DeepSeek", "ChatGPT", "Gemini", "Mistral", "Local LLM"]
}
```

### POST /llm/query

Query the LLM.

**Request:**
```json
{
  "prompt": "What is the area of Africa?",
  "system_prompt": "You are AETHERA, a geometric analysis assistant."
}
```

**Response:**
```json
{
  "text": "Africa's area is approximately 30.37 million km²...",
  "provider": "GLM-5.2 (Z.ai)",
  "success": true
}
```

---

## AICS Coordinates

### GET /aics/coordinates/{region_name}

Get AETHERA Intrinsic Coordinate System coordinates.

**Response:**
```json
{
  "region": "Africa",
  "aics_coordinates": {
    "barycentric_x": 2494.4,
    "barycentric_y": -861.7,
    "scale_z": 5511.0
  },
  "intrinsic_direction": {
    "azimuth_rad": -0.33,
    "azimuth_deg": -18.9,
    "distance_from_origin": 2612.5
  },
  "physical_area_km2": 30370000
}
```

---

## Error Codes

| Code | Meaning | Fix |
|------|---------|-----|
| 400 | Bad Request | Check request body format |
| 404 | Not Found | Check endpoint path |
| 500 | Internal Server Error | Check backend logs |

---

## Rate Limiting

- No rate limiting on local deployment
- Railway free tier: 100 requests/hour
- Vercel free tier: 1000 requests/hour
