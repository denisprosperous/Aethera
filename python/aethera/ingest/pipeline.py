"""AETHERA ingest pipeline (v10.2 — Tabula Rasa, no coordinates).

Two ingestion modes:

Mode A (user survey): The user provides a CSV of absolute distances:
    point_A, point_B, distance_meters
  These are stored directly as measured. No coordinates.

Mode B (topology bootstrapping): We extract ONLY adjacency topology
  from Natural Earth shapefiles. All edge lengths are 1.0 placeholders.
  The solver (Agent 2) infers true lengths from global area closure.

CRITICAL: No lon/lat, no x/y/z, no projections, no sphere, no ellipsoid.
"""

import argparse
import os
import subprocess

from .schema import create_schema
from .db import Database
from .natural_earth import get_region_topology, REGIONS, download_shapefiles
from .geometry import placeholder_length, parse_survey_csv


def ingest_region(region: str, commit_and_push: bool = False) -> dict:
    """Ingest all polygon topology for a region (Mode B bootstrapping).
    Uses batch inserts for performance."""
    print(f"\n{'='*60}")
    print(f"Ingesting region (Mode B topology): {region}")
    print(f"{'='*60}")

    with Database() as db:
        db.update_region_status(region, "processing")

    polygons = get_region_topology(region)
    if not polygons:
        with Database() as db:
            db.update_region_status(region, "done")
        return {"region": region, "faces": 0, "edges": 0, "points": 0, "commit_hash": None}

    print(f"  Found {len(polygons)} polygons (topology only, no coordinates).")

    total_edges = 0
    total_points = 0
    faces_ingested = 0

    with Database() as db:
        for name, face_type, rings in polygons:
            for ring_idx, ring_labels in enumerate(rings):
                if len(ring_labels) < 3:
                    continue

                # Batch-create all points for this ring.
                labels_regions = [(label, region) for label in ring_labels]
                point_map = db.batch_create_points(labels_regions, source="topology")
                point_ids = [point_map[(label, region)] for label in ring_labels]
                total_points += len(set(point_ids))

                # Batch-create all edges with placeholder lengths (Mode B).
                n = len(point_ids)
                edge_specs = []
                for i in range(n):
                    p1 = point_ids[i]
                    p2 = point_ids[(i + 1) % n]
                    if p1 == p2:
                        continue
                    edge_specs.append((p1, p2, placeholder_length(), region, "placeholder", "topology"))
                edge_ids = db.batch_create_edges(edge_specs)
                edge_ids = [eid for eid in edge_ids if eid is not None]
                total_edges += len(edge_ids)

                # Insert the face.
                face_name = name if ring_idx == 0 else f"{name}_ring{ring_idx}"
                db.insert_face(
                    name=face_name, face_type=face_type, region=region,
                    edge_ids=edge_ids, point_ids=point_ids,
                    properties={"ring_index": ring_idx, "point_count": n},
                )
                faces_ingested += 1

                if faces_ingested % 5 == 0:
                    print(f"  Ingested {faces_ingested} polygons ({total_edges} edges so far)...")

        db.update_region_status(region, "done", total_edges, faces_ingested, total_points)

    print(f"  Done: {faces_ingested} faces, {total_edges} edges, {total_points} points (placeholder lengths).")

    commit_hash = None
    if commit_and_push:
        commit_hash = _git_commit_and_push(region)
    if commit_hash:
        with Database() as db:
            db.update_region_status(region, "done", total_edges, faces_ingested, total_points, commit_hash)

    return {"region": region, "faces": faces_ingested, "edges": total_edges, "points": total_points, "commit_hash": commit_hash}


def ingest_survey_csv(csv_text: str, region: str = "user_survey", commit_and_push: bool = False) -> dict:
    """Ingest Mode A user-supplied survey data (absolute distances)."""
    print(f"\n{'='*60}\nIngesting Mode A user survey ({region})\n{'='*60}")
    edges_data = parse_survey_csv(csv_text)
    print(f"  Parsed {len(edges_data)} survey edges.")
    total_edges = 0
    point_cache = {}
    with Database() as db:
        db.update_region_status(region, "processing")
        # Batch-create all points first.
        labels_regions = set()
        for s, t, _ in edges_data:
            labels_regions.add((s, region))
            labels_regions.add((t, region))
        point_map = db.batch_create_points(list(labels_regions), source="survey")
        # Batch-create all edges.
        edge_specs = []
        for s_label, t_label, distance in edges_data:
            sid = point_map[(s_label, region)]
            tid = point_map[(t_label, region)]
            edge_specs.append((sid, tid, distance, region, "measured", "survey"))
        edge_ids = db.batch_create_edges(edge_specs)
        total_edges = len([e for e in edge_ids if e is not None])
        db.update_region_status(region, "done", total_edges, 0, len(point_map))
    print(f"  Done: {total_edges} measured edges, {len(point_map)} points.")
    commit_hash = None
    if commit_and_push:
        commit_hash = _git_commit_and_push(f"survey_{region}")
    return {"region": region, "edges": total_edges, "points": len(point_map), "commit_hash": commit_hash}


def ingest_all(commit_and_push: bool = False) -> list:
    create_schema()
    download_shapefiles()
    results = []
    for region in REGIONS:
        result = ingest_region(region, commit_and_push=commit_and_push)
        results.append(result)
    return results


def _git_commit_and_push(label: str) -> str:
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    try:
        subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True, capture_output=True)
        commit_msg = f"Ingested region (Mode B topology): {label}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir, check=True, capture_output=True)
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True)
        commit_hash = result.stdout.strip()
        print(f"  Committed: {commit_hash[:8]}")
        try:
            subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True, capture_output=True, timeout=30)
            print(f"  Pushed to GitHub.")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"  Push deferred: {e}")
        return commit_hash
    except subprocess.CalledProcessError as e:
        print(f"  Git commit failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="AETHERA data ingestion (v10.2 — no coordinates)")
    parser.add_argument("--region", type=str, help="Region to ingest (Mode B topology)")
    parser.add_argument("--all", action="store_true", help="Ingest all regions (Mode B)")
    parser.add_argument("--survey", type=str, help="Path to Mode A survey CSV file")
    parser.add_argument("--push", action="store_true", help="Commit and push after ingestion")
    args = parser.parse_args()
    if args.survey:
        with open(args.survey) as f:
            csv_text = f.read()
        result = ingest_survey_csv(csv_text, region="user_survey", commit_and_push=args.push)
        print(f"\nResult: {result}")
    elif args.all:
        results = ingest_all(commit_and_push=args.push)
        print(f"\n{'='*60}\nIngestion summary:")
        for r in results:
            print(f"  {r['region']:20s}  faces={r.get('faces',0):5d}  edges={r['edges']:6d}")
    elif args.region:
        create_schema()
        download_shapefiles()
        result = ingest_region(args.region, commit_and_push=args.push)
        print(f"\nResult: {result}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
