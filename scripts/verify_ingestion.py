#!/usr/bin/env python3
"""AETHERA — ingestion verification (v25.0).

Checks Phase-1 acceptance criteria and prints a markdown status block:
  * >= 200 regions with source ETOPO1_GLOBAL
  * no zero-area regions
  * total surface area within 2% of Earth's accepted 510,072,000 km^2

Exit code 0 when all criteria hold, 1 otherwise.
"""

import os
import sys
from datetime import datetime, timezone

import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    # Default mirrors python/aethera/ingest/db.py
    "postgresql://neondb_owner:npg_i7I6oGlzgpmu@"
    "ep-small-fire-awt6hp2b.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require",
)

EARTH_TOTAL_KM2 = 510_072_000  # accepted global surface area
MIN_REGIONS = 200


def main() -> int:
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=20)
    cur = conn.cursor()

    cur.execute(
        "SELECT computed_from, COUNT(*), "
        "SUM(CASE WHEN area_m2 = 0 THEN 1 ELSE 0 END) "
        "FROM physical_truth_srtm GROUP BY computed_from"
    )
    by_source = cur.fetchall()

    cur.execute("SELECT COUNT(*), SUM(CASE WHEN area_m2 = 0 THEN 1 ELSE 0 END) "
                "FROM physical_truth_srtm")
    total_rows, zero_area = cur.fetchone()
    cur.execute("SELECT COALESCE(SUM(area_m2), 0) / 1e6 FROM physical_truth_srtm")
    total_km2 = float(cur.fetchone()[0])
    cur.execute("SELECT region_name, area_m2/1e6 FROM physical_truth_srtm "
                "ORDER BY area_m2 DESC LIMIT 10")
    top10 = cur.fetchall()
    conn.close()

    etopo_rows = next((c for s, c, _z in by_source
                       if s and "ETOPO1" in s.upper()), 0)
    dev_pct = abs(total_km2 - EARTH_TOTAL_KM2) / EARTH_TOTAL_KM2 * 100.0

    ok_regions = etopo_rows >= MIN_REGIONS
    ok_zero = (zero_area or 0) == 0
    ok_total = dev_pct <= 2.0
    all_ok = ok_regions and ok_zero and ok_total

    lines = [
        "# ETOPO1 Ingestion Status",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Regions (ETOPO1_GLOBAL): **{etopo_rows}** "
        f"(criterion: >= {MIN_REGIONS}) {'OK' if ok_regions else 'FAIL'}",
        f"- Zero-area regions: **{zero_area or 0}** "
        f"(criterion: 0) {'OK' if ok_zero else 'FAIL'}",
        f"- Total surface: **{total_km2:,.0f} km2** vs accepted "
        f"{EARTH_TOTAL_KM2:,} km2 (deviation {dev_pct:.2f}%) "
        f"{'OK' if ok_total else 'FAIL'}",
        "",
        "## Rows by source",
        "",
    ]
    for src, cnt, zeros in by_source:
        lines.append(f"- {src}: {cnt} rows, {zeros or 0} zero-area")
    lines += ["", "## Largest 10 regions", ""]
    for name, km2 in top10:
        lines.append(f"- {name}: {km2:,.0f} km2")
    lines += ["", f"**Overall: {'PASS' if all_ok else 'FAIL'}**", ""]

    print("\n".join(lines))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
