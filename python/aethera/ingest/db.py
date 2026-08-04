"""Database helpers for AETHERA ingestion (v10.2 — no coordinates).

All functions operate on point IDs and edge lengths only. No x/y/z,
no lon/lat. Mode A: user-supplied absolute distances. Mode B: 1.0
placeholders for topology bootstrapping."""

import os
import psycopg2
from psycopg2.extras import Json, execute_values

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_i7I6oGlzgpmu@ep-small-fire-awt6hp2b.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require",
)


class Database:
    """Context-managed PostgreSQL connection."""

    def __init__(self, url: str = None):
        self.url = url or DATABASE_URL
        self.conn = None
        self.cur = None
        self._point_cache = {}  # (label, region) -> id

    def __enter__(self):
        self.conn = psycopg2.connect(self.url)
        self.conn.autocommit = False
        self.cur = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.cur.close()
        self.conn.close()

    # ---- Points (no coordinates) -------------------------------------

    def get_or_create_point(self, label, region, source="topology"):
        """Insert a point (identified by label+region) and return its ID.
        Uses cache to avoid redundant DB round-trips."""
        cache_key = (label, region)
        if cache_key in self._point_cache:
            return self._point_cache[cache_key]
        self.cur.execute(
            "INSERT INTO points (label, region, source) VALUES (%s, %s, %s) "
            "ON CONFLICT DO NOTHING RETURNING id",
            (label, region, source),
        )
        row = self.cur.fetchone()
        if row:
            pid = row[0]
        else:
            self.cur.execute(
                "SELECT id FROM points WHERE label=%s AND region=%s",
                (label, region),
            )
            pid = self.cur.fetchone()[0]
        self._point_cache[cache_key] = pid
        return pid

    def batch_create_points(self, labels_regions, source="topology"):
        """Batch-insert points using execute_values (fast).
        Returns dict mapping (label, region) -> point_id."""
        if not labels_regions:
            return {}
        from psycopg2.extras import execute_values
        unique = list(set(labels_regions))
        values = [(label, region, source) for label, region in unique]
        # Insert all (ON CONFLICT DO NOTHING), then fetch IDs in bulk.
        execute_values(
            self.cur,
            "INSERT INTO points (label, region, source) VALUES %s "
            "ON CONFLICT (label, region) WHERE label IS NOT NULL DO NOTHING",
            values,
            page_size=500,
        )
        # Fetch all IDs by region+label.
        labels_by_region = {}
        for label, region in unique:
            labels_by_region.setdefault(region, []).append(label)
        result = {}
        for region, labels in labels_by_region.items():
            self.cur.execute(
                "SELECT label, id FROM points WHERE region=%s AND label = ANY(%s)",
                (region, labels),
            )
            for label, pid in self.cur.fetchall():
                result[(label, region)] = pid
                self._point_cache[(label, region)] = pid
        return result

    # ---- Edges (raw scalar lengths) ----------------------------------

    def get_or_create_edge(self, source_id, target_id, length_raw, region,
                            length_mode="placeholder", source="topology"):
        """Insert an edge (deduplicated by source,target pair) and return its ID."""
        a, b = (source_id, target_id) if source_id < target_id else (target_id, source_id)
        self.cur.execute(
            "INSERT INTO edges (source_point_id, target_point_id, length_raw, length_mode, region, source) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (source_point_id, target_point_id) DO UPDATE SET "
            "length_raw=EXCLUDED.length_raw, length_mode=EXCLUDED.length_mode "
            "RETURNING id",
            (a, b, length_raw, length_mode, region, source),
        )
        return self.cur.fetchone()[0]

    def batch_create_edges(self, edge_specs):
        """Batch-insert edges using execute_values (fast).
        Returns list of edge IDs in the same order."""
        if not edge_specs:
            return []
        from psycopg2.extras import execute_values
        normalised = []
        for sid, tid, length, region, mode, src in edge_specs:
            a, b = (sid, tid) if sid < tid else (tid, sid)
            # Column order: (source_point_id, target_point_id, length_raw, length_mode, region, source)
            normalised.append((a, b, length, mode, region, src))
        execute_values(
            self.cur,
            "INSERT INTO edges (source_point_id, target_point_id, length_raw, length_mode, region, source) "
            "VALUES %s ON CONFLICT (source_point_id, target_point_id) DO NOTHING",
            normalised,
            page_size=500,
        )
        # Fetch all IDs for each region in one query.
        # normalised tuples are: (a, b, length, mode, region, src)
        regions = set(n[4] for n in normalised)
        id_map = {}
        for region in regions:
            self.cur.execute(
                "SELECT source_point_id, target_point_id, id FROM edges WHERE region=%s",
                (region,),
            )
            for sid, tid, eid in self.cur.fetchall():
                id_map[(sid, tid, region)] = eid
        return [id_map.get((n[0], n[1], n[4])) for n in normalised]

    # ---- Faces -------------------------------------------------------

    def insert_face(self, name, face_type, region, edge_ids, point_ids, properties=None):
        """Insert a face (polygon) with its ordered edge and point lists."""
        self.cur.execute(
            "INSERT INTO faces (name, type, region, edge_ids, point_ids, properties) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (name, face_type, region, edge_ids, point_ids, Json(properties or {})),
        )
        return self.cur.fetchone()[0]

    # ---- Region status -----------------------------------------------

    def update_region_status(self, region, status, edge_count=0, face_count=0,
                              point_count=0, commit_hash=None):
        self.cur.execute(
            "INSERT INTO region_status (region, status, edge_count, face_count, point_count, last_commit_hash, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW()) "
            "ON CONFLICT (region) DO UPDATE SET "
            "status=EXCLUDED.status, edge_count=EXCLUDED.edge_count, "
            "face_count=EXCLUDED.face_count, point_count=EXCLUDED.point_count, "
            "last_commit_hash=EXCLUDED.last_commit_hash, updated_at=NOW()",
            (region, status, edge_count, face_count, point_count, commit_hash),
        )

    def get_region_status(self, region):
        self.cur.execute(
            "SELECT status, edge_count, face_count, point_count, last_commit_hash "
            "FROM region_status WHERE region=%s",
            (region,),
        )
        row = self.cur.fetchone()
        if row:
            return {"status": row[0], "edge_count": row[1], "face_count": row[2],
                    "point_count": row[3], "last_commit_hash": row[4]}
        return None

    def get_all_region_status(self):
        self.cur.execute(
            "SELECT region, status, edge_count, face_count, point_count, last_commit_hash "
            "FROM region_status ORDER BY region"
        )
        return [
            {"region": r[0], "status": r[1], "edge_count": r[2], "face_count": r[3],
             "point_count": r[4], "last_commit_hash": r[5]}
            for r in self.cur.fetchall()
        ]

    # ---- Counts ------------------------------------------------------

    def count_edges(self, region=None):
        if region:
            self.cur.execute("SELECT COUNT(*) FROM edges WHERE region=%s", (region,))
        else:
            self.cur.execute("SELECT COUNT(*) FROM edges")
        return self.cur.fetchone()[0]

    def count_points(self, region=None):
        if region:
            self.cur.execute("SELECT COUNT(*) FROM points WHERE region=%s", (region,))
        else:
            self.cur.execute("SELECT COUNT(*) FROM points")
        return self.cur.fetchone()[0]

    def count_faces(self, region=None):
        if region:
            self.cur.execute("SELECT COUNT(*) FROM faces WHERE region=%s", (region,))
        else:
            self.cur.execute("SELECT COUNT(*) FROM faces")
        return self.cur.fetchone()[0]

    # ---- Global area invariants -------------------------------------

    def set_global_area_invariant(self, name, total_area_m2, source="user-supplied", notes=None):
        self.cur.execute(
            "INSERT INTO global_area_invariants (name, total_area_m2, source, notes) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET total_area_m2=EXCLUDED.total_area_m2, "
            "source=EXCLUDED.source, notes=EXCLUDED.notes",
            (name, total_area_m2, source, notes),
        )

    def get_global_area_invariant(self, name):
        self.cur.execute(
            "SELECT total_area_m2, source, notes FROM global_area_invariants WHERE name=%s",
            (name,),
        )
        row = self.cur.fetchone()
        if row:
            return {"total_area_m2": row[0], "source": row[1], "notes": row[2]}
        return None

    # ---- Solver data retrieval --------------------------------------

    def get_region_edges(self, region):
        """Return all edges for a region as list of dicts."""
        self.cur.execute(
            "SELECT id, source_point_id, target_point_id, length_raw, length_mode "
            "FROM edges WHERE region=%s ORDER BY id",
            (region,),
        )
        return [
            {"id": r[0], "source": r[1], "target": r[2],
             "length": r[3], "mode": r[4]}
            for r in self.cur.fetchall()
        ]

    def get_region_faces(self, region):
        """Return all faces for a region."""
        self.cur.execute(
            "SELECT id, name, type, edge_ids, point_ids, properties "
            "FROM faces WHERE region=%s ORDER BY id",
            (region,),
        )
        return [
            {"id": r[0], "name": r[1], "type": r[2], "edge_ids": r[3],
             "point_ids": r[4], "properties": r[5]}
            for r in self.cur.fetchall()
        ]

    def get_all_regions(self):
        """Return all regions with their status."""
        return self.get_all_region_status()
