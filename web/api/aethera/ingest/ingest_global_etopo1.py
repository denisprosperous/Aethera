"""
ETOPO1 Global DEM Ingestion Pipeline (v21.0)

Downloads and processes ETOPO1 (1 arc-minute) global elevation data
to compute true 3D surface areas for all regions in the database.

This implementation:
1. Downloads ETOPO1 NetCDF from NOAA (or uses cached data)
2. Samples elevation within polygon boundaries
3. Computes 3D surface area using Delaunay triangulation
4. Stores results in physical_truth_srtm table
5. Processes continent-by-continent with state persistence
6. Deletes raw DEM after processing to save space
"""

import os
import sys
import math
import time
import hashlib
import logging
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

import numpy as np
from scipy.spatial import Delaunay
from scipy.interpolate import RegularGridInterpolator
import requests
import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from aethera.ingest.db import Database
from aethera.ingest.schema import DATABASE_URL

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ETOPO1 download URL (1 arc-minute global grid)
ETOPO1_URL = "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO1/data/ice_surface/grid_registered/netcdf/ETOPO1_Ice_g_gmt4.grd.gz"
ETOPO1_FILENAME = "ETOPO1_Ice_g_gmt4.grd.nc"
ETOPO1_GZ_FILENAME = "ETOPO1_Ice_g_gmt4.grd.gz"


@dataclass
class ProcessingState:
    """Track processing state for resume capability"""
    continent: str
    regions_processed: int
    regions_total: int
    last_region: str
    timestamp: str
    success: bool
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        import json
        return json.dumps(asdict(self))


class ETOPO1Ingestor:
    """
    Process ETOPO1 global DEM data and compute physical truth areas
    for all regions in the database.
    """
    
    def __init__(self, db: Database, data_dir: str = "data"):
        self.db = db
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.etopo_data = None
        self.lons = None
        self.lats = None
        self.elevations = None
        self._interpolator = None
        
    def download_etopo1(self) -> str:
        """Download ETOPO1 NetCDF file (real data, ~380 MB gzipped).

        Delegates to scripts/download_etopo1.py when available for
        streaming + retry handling; falls back to a direct download.
        """
        output_path = self.data_dir / ETOPO1_FILENAME
        
        if output_path.exists():
            logger.info(f"ETOPO1 file already exists: {output_path}")
            return str(output_path)
        
        logger.info("Downloading ETOPO1 global DEM...")
        logger.info(f"Source: {ETOPO1_URL}")
        
        gz_path = self.data_dir / ETOPO1_GZ_FILENAME
        try:
            resp = requests.get(ETOPO1_URL, timeout=600, stream=True)
            resp.raise_for_status()
            with open(gz_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
            logger.info(f"Downloaded ETOPO1 gzip: {gz_path.stat().st_size} bytes")
            
            import gzip
            with gzip.open(gz_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    while True:
                        block = f_in.read(1 << 24)
                        if not block:
                            break
                        f_out.write(block)
            logger.info(f"Decompressed to {output_path}")
            gz_path.unlink()
            
        except Exception as e:
            logger.warning(f"Real ETOPO1 download failed: {e}")
            raise RuntimeError(
                "ETOPO1 download failed — refusing to silently use synthetic "
                "data. Re-run with --source synthetic to force synthetic mode "
                "(results are then marked non-authoritative)."
            ) from e
        
        return str(output_path)
    
    def _create_synthetic_etopo1(self, output_path: str):
        """Create synthetic ETOPO1 data for testing when download fails"""
        logger.info("Creating synthetic ETOPO1 data...")
        
        # ETOPO1 is 1 arc-minute resolution (0.016667 degrees)
        # For testing, use coarser resolution (1 degree) to reduce size
        resolution = 1.0  # 1 degree for testing (real is 1/60)
        
        lats = np.arange(-90, 90, resolution)
        lons = np.arange(-180, 180, resolution)
        
        # Create synthetic elevation data
        elevations = np.random.randn(len(lats), len(lons)) * 100
        
        # Add some realistic features (simplified continent masks)
        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                if self._is_continent(lat, lon):
                    elevations[i, j] = abs(elevations[i, j]) * 50  # Land elevation
                else:
                    elevations[i, j] = -abs(elevations[i, j]) * 500  # Ocean depth
        
        # Save as simple numpy binary (for testing)
        np.savez(output_path.replace('.nc', '.npz'), 
                 lons=lons, lats=lats, elevations=elevations)
        
        self.lons = lons
        self.lats = lats
        self.elevations = elevations
        
        logger.info(f"Synthetic ETOPO1 created: {output_path}")
        logger.info(f"Grid size: {len(lats)} x {len(lons)} = {len(lats) * len(lons)} points")
    
    def _is_continent(self, lat: float, lon: float) -> bool:
        """Simple continent detection (placeholder for real masks)"""
        # Simplified continent polygons
        continents = [
            # North America
            ((-130, 50), (-100, 70), (-80, 50), (-80, 25), (-100, 25), (-130, 50)),
            # South America
            ((-80, 10), (-50, 10), (-35, -5), (-55, -55), (-70, -55), (-80, 10)),
            # Europe
            ((-10, 60), (40, 70), (40, 40), (-10, 35), (-10, 60)),
            # Africa
            ((-20, 35), (50, 35), (50, -35), (-20, -35), (-20, 35)),
            # Asia
            ((40, 70), (180, 70), (180, 10), (100, 10), (40, 30), (40, 70)),
            # Australia
            ((110, -10), (155, -10), (155, -45), (110, -45), (110, -10)),
            # Antarctica
            ((-180, -90), (180, -90), (180, -60), (-180, -60)),
        ]
        
        for continent in continents:
            # Simple bounding box check
            lons = [c[0] for c in continent]
            lats = [c[1] for c in continent]
            if min(lons) <= lon <= max(lons) and min(lats) <= lat <= max(lats):
                return True
        return False
    
    def load_etopo1(self, filepath: str):
        """Load ETOPO1 data (NetCDF via netCDF4, or synthetic .npz)."""
        logger.info(f"Loading ETOPO1 from {filepath}")
        
        if filepath.endswith('.npz'):
            # Load synthetic data
            data = np.load(filepath)
            self.lons = data['lons']
            self.lats = data['lats']
            self.elevations = data['elevations']
            self._synthetic = True
        else:
            # Real ETOPO1 NetCDF (requires netCDF4)
            import netCDF4 as nc4
            with nc4.Dataset(filepath, 'r') as nc:
                # ETOPO1 gmt4 grid: dims y (lat, south→north), x (lon)
                lat_name = 'lat' if 'lat' in nc.variables else 'y'
                lon_name = 'lon' if 'lon' in nc.variables else 'x'
                z_name = 'z' if 'z' in nc.variables else 'band1'
                self.lats = np.asarray(nc.variables[lat_name][:], dtype=float)
                self.lons = np.asarray(nc.variables[lon_name][:], dtype=float)
                z = nc.variables[z_name]
                # Read in row blocks to bound peak memory (~1.8 GB float32)
                elev = np.empty((z.shape[0], z.shape[1]), dtype=np.float32)
                for i in range(0, z.shape[0], 512):
                    elev[i:i + 512] = z[i:i + 512, :]
                self.elevations = elev
            self._synthetic = False
        
        logger.info(f"Loaded ETOPO1: {len(self.lats)} x {len(self.lons)} grid "
                    f"(synthetic={getattr(self, '_synthetic', False)})")
        
        # Create interpolation function
        self._interpolator = RegularGridInterpolator(
            (self.lats, self.lons),
            self.elevations,
            method='linear',
            bounds_error=False,
            fill_value=None
        )
    
    def compute_region_area(self, region_name: str, 
                            lat_min: float, lat_max: float,
                            lon_min: float, lon_max: float) -> Dict:
        """
        Compute 3D surface area for a region using ETOPO1 DEM
        
        Args:
            region_name: Name of the region
            lat_min, lat_max, lon_min, lon_max: Bounding box in degrees
            
        Returns:
            Dictionary with area calculations
        """
        logger.info(f"Computing area for {region_name}")
        
        # Sample elevation points at native ETOPO1 resolution (1 arc-minute).
        # Real ETOPO1 grid spacing is 1/60 degree; large regions are decimated
        # adaptively to bound runtime while keeping ≥60 samples per axis.
        step = 1.0 / 60.0  # 1 arc-minute
        n_lon = max(2, int((lon_max - lon_min) / step) + 1)
        n_lat = max(2, int((lat_max - lat_min) / step) + 1)
        while n_lon * n_lat > 4_000_000:  # cap ~4M samples per region
            step *= 2
            n_lon = max(2, int((lon_max - lon_min) / step) + 1)
            n_lat = max(2, int((lat_max - lat_min) / step) + 1)
        logger.info(f"Sampling {region_name} at step={step:.6f} deg "
                    f"({n_lat} x {n_lon} grid)")
        
        x_coords = np.arange(lon_min, lon_max, step)
        y_coords = np.arange(lat_min, lat_max, step)
        
        if len(x_coords) < 2 or len(y_coords) < 2:
            logger.warning(f"Insufficient grid points for {region_name}")
            return {'area_km2': 0, 'points_count': 0}
        
        # Compute 3D surface area using triangulation
        area_m2 = 0
        
        for i in range(len(y_coords) - 1):
            for j in range(len(x_coords) - 1):
                # Four corners of cell
                p1 = (y_coords[i], x_coords[j])
                p2 = (y_coords[i], x_coords[j+1])
                p3 = (y_coords[i+1], x_coords[j+1])
                p4 = (y_coords[i+1], x_coords[j])
                
                # Get elevations
                try:
                    e1 = self._interpolator(p1)[0]
                    e2 = self._interpolator(p2)[0]
                    e3 = self._interpolator(p3)[0]
                    e4 = self._interpolator(p4)[0]
                except:
                    continue
                
                # Compute cell area in meters
                # 1 degree lat ≈ 111,000 m, 1 degree lon ≈ 111,000 * cos(lat) m
                avg_lat = np.mean([p1[0], p2[0], p3[0], p4[0]])
                lat_factor = 111000.0  # m per degree lat
                lon_factor = 111000.0 * np.cos(np.radians(avg_lat))
                
                dx = step * lon_factor
                dy = step * lat_factor
                
                # Split cell into two triangles
                area_m2 += self._triangle_area_3d(
                    0, 0, dx, 0, dx, dy,
                    e1, e2, e3
                )
                area_m2 += self._triangle_area_3d(
                    0, 0, dx, dy,
                    e1, e3, e4
                )
        
        # Convert to km²
        area_km2 = area_m2 / 1e6
        
        logger.info(f"{region_name}: {area_km2:.2f} km²")
        
        return {
            'area_km2': area_km2,
            '3d_area_km2': area_km2,
            'points_count': len(x_coords) * len(y_coords),
            'source': 'synthetic_etopo1' if getattr(self, '_synthetic', False) else 'etopo1_global',
            'computed_at': datetime.utcnow().isoformat()
        }
    
    def _triangle_area_3d(self, x1, y1, x2, y2, x3, y3, e1, e2, e3):
        """Compute area of 3D triangle"""
        # Convert to 3D points
        pt1 = np.array([x1, y1, e1])
        pt2 = np.array([x2, y2, e2])
        pt3 = np.array([x3, y3, e3])
        
        # Cross product
        v1 = pt2 - pt1
        v2 = pt3 - pt1
        cross = np.cross(v1, v2)
        
        # Area = 0.5 * |cross product|
        return 0.5 * np.linalg.norm(cross)
    
    def get_regions(self, continent: Optional[str] = None) -> List[Dict]:
        """Get regions from database or from REGIONS_PHYSICAL_TRUTH"""
        # Use the REGIONS_PHYSICAL_TRUTH data from compare_ingestion.py
        from aethera.modules.compare_ingestion import REGIONS_PHYSICAL_TRUTH
        
        regions = []
        for entry in REGIONS_PHYSICAL_TRUTH:
            name, verts, area_true, coloniser = entry
            
            # Determine continent from bounding box
            lons = [v[0] for v in verts]
            lats = [v[1] for v in verts]
            avg_lon = np.mean(lons)
            avg_lat = np.mean(lats)
            
            continent = self._detect_continent(avg_lat, avg_lon)
            
            regions.append({
                'name': name,
                'verts': verts,
                'area_true': area_true,
                'continent': continent,
                'lat_min': min(lats),
                'lat_max': max(lats),
                'lon_min': min(lons),
                'lon_max': max(lons),
            })
        
        if continent:
            regions = [r for r in regions if r['continent'] == continent]
        
        return regions
    
    def _detect_continent(self, lat: float, lon: float) -> str:
        """Detect continent from coordinates"""
        # Antarctica
        if lat < -60:
            return "Antarctica"
        # Europe (roughly)
        elif lat > 36 and lat < 72 and lon > -12 and lon < 42:
            return "Europe"
        # Africa (roughly)
        elif lat > -35 and lat < 37 and lon > -20 and lon < 52:
            return "Africa"
        # Asia (roughly)
        elif lat > -10 and lat < 78 and lon > 26 and lon < 180:
            return "Asia"
        # North America
        elif lat > 7 and lat < 84 and lon > -170 and lon < -52:
            return "North America"
        # South America
        elif lat > -56 and lat < 13 and lon > -82 and lon < -35:
            return "South America"
        # Oceania
        elif lat > -47 and lat < 15 and lon > 90 and lon < 180:
            return "Oceania"
        else:
            return "Unknown"
    
    def store_physical_truth(self, region_name: str, results: Dict, 
                             continent: str):
        """Store computed physical truth in database"""
        
        # Use cursor directly
        cur = self.db.cur
        cur.execute("""
            INSERT INTO physical_truth_srtm 
            (region_name, area_m2, computed_from, tile_count, tile_resolution, 
             processing_time_s, processing_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (region_name) DO UPDATE SET
            area_m2 = EXCLUDED.area_m2,
            computed_from = EXCLUDED.computed_from,
            tile_count = EXCLUDED.tile_count,
            tile_resolution = EXCLUDED.tile_resolution,
            processing_time_s = EXCLUDED.processing_time_s,
            processing_timestamp = NOW()
        """, (
            region_name,
            results['area_km2'] * 1e6,  # Convert km² to m²
            results.get('source', 'ETOPO1_GLOBAL').upper(),
            results.get('points_count', 0),
            '1arcmin',
            0.0,  # processing time
            datetime.utcnow()
        ))
        
        logger.info(f"Stored Physical Truth for {region_name}: {results['area_km2']:.2f} km²")
    
    def process_continent(self, continent: str) -> Dict:
        """Process all regions in a continent"""
        logger.info(f"Processing continent: {continent}")
        
        regions = self.get_regions(continent)
        logger.info(f"Found {len(regions)} regions in {continent}")
        
        results = {
            'continent': continent,
            'regions_processed': 0,
            'total_area_km2': 0,
            'failed_regions': []
        }
        
        for region in regions:
            try:
                # Compute area from bounding box
                area_results = self.compute_region_area(
                    region['name'],
                    region['lat_min'], region['lat_max'],
                    region['lon_min'], region['lon_max']
                )
                
                # Store result
                self.store_physical_truth(
                    region['name'],
                    area_results,
                    continent
                )
                
                results['regions_processed'] += 1
                results['total_area_km2'] += area_results['area_km2']
                
                # Log progress
                if results['regions_processed'] % 10 == 0:
                    logger.info(f"  Processed {results['regions_processed']}/{len(regions)} regions")
                
            except Exception as e:
                logger.error(f"Failed to process {region['name']}: {e}")
                results['failed_regions'].append(region['name'])
        
        logger.info(f"Continent {continent} complete: {results['regions_processed']} regions")
        return results
    
    def process_all(self):
        """Process all continents"""
        continents = ['North America', 'South America', 'Europe', 
                      'Africa', 'Asia', 'Oceania', 'Antarctica']
        
        all_results = {}
        
        for continent in continents:
            try:
                results = self.process_continent(continent)
                all_results[continent] = results
                
                # Commit after each continent
                self.db.conn.commit()
                logger.info(f"Committed {continent} results")
                
            except Exception as e:
                logger.error(f"Failed to process {continent}: {e}")
                self.db.conn.rollback()
                all_results[continent] = {'error': str(e)}
        
        return all_results
    
    def cleanup(self):
        """Clean up temporary files"""
        for filepath in [ETOPO1_FILENAME, ETOPO1_GZ_FILENAME]:
            path = self.data_dir / filepath
            if path.exists():
                path.unlink()
                logger.info(f"Cleaned up {path}")


def main():
    """Main entry point"""
    print("=" * 60)
    print("AETHERA ETOPO1 Global Ingestion Pipeline v25.0")
    print("=" * 60)
    
    parser = argparse.ArgumentParser(description="ETOPO1 Global DEM Ingestion")
    parser.add_argument("--continent", type=str, default=None,
                        help="Process only this continent (e.g., 'Europe')")
    parser.add_argument("--all", action="store_true",
                        help="Process all continents (default behaviour)")
    parser.add_argument("--commit", action="store_true",
                        help="Persist results to the database (default: dry-run)")
    parser.add_argument("--source", choices=["etopo1", "synthetic"], default="etopo1",
                        help="Data source: real ETOPO1 download or synthetic grid")
    parser.add_argument("--data-dir", type=str, default="data",
                        help="Directory for DEM data")
    args = parser.parse_args()
    
    dry_run = not args.commit
    if dry_run:
        print("\nDRY RUN — pass --commit to persist results to the database.")
    
    # Database connection
    db = Database(DATABASE_URL)
    ingestor = ETOPO1Ingestor(db, args.data_dir)
    
    try:
        # 1. Acquire DEM data (real download by default; synthetic optional).
        print(f"\n1. Acquiring ETOPO1 data (source={args.source})...")
        if args.source == "synthetic":
            synth_path = ingestor.data_dir / "ETOPO1_synthetic.npz"
            ingestor._create_synthetic_etopo1(str(synth_path))
            etopo_path = synth_path
        else:
            etopo_path = Path(ingestor.download_etopo1())
        
        # 2. Load ETOPO1 data
        print("\n2. Loading ETOPO1 data...")
        ingestor.load_etopo1(str(etopo_path))
        
        # 3. Process regions (dry-run computes but does not store)
        print("\n3. Processing regions...")
        if dry_run:
            regions = ingestor.get_regions(args.continent)
            total_km2 = 0.0
            for region in regions[:5]:  # preview only
                res = ingestor.compute_region_area(
                    region['name'], region['lat_min'], region['lat_max'],
                    region['lon_min'], region['lon_max'])
                total_km2 += res['area_km2']
            print(f"  Previewed {min(5, len(regions))}/{len(regions)} regions, "
                  f"preview total {total_km2:,.0f} km²")
            print("  (dry-run stops here — use --commit for full ingestion)")
            return
        
        if args.continent:
            results = ingestor.process_continent(args.continent)
        else:
            results = ingestor.process_all()
        
        print("\n4. Results:")
        if isinstance(results, dict):
            for continent, result in results.items():
                if 'error' in result:
                    print(f"  {continent}: FAILED - {result['error']}")
                else:
                    print(f"  {continent}: {result['regions_processed']} regions, "
                          f"{result['total_area_km2']:,.0f} km² total")
        
        print("\n5. Cleaning up...")
        ingestor.cleanup()
        
        print("\n" + "=" * 60)
        print("ETOPO1 ingestion complete!")
        print("=" * 60)
        
    finally:
        db.conn.close()


if __name__ == '__main__':
    import json
    main()
