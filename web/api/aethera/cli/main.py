"""AETHERA CLI — command-line interface."""
import sys
import argparse
import asyncio

def main():
    parser = argparse.ArgumentParser(description="AETHERA v0.2.0 — Sovereign Computational Geometry Platform")
    parser.add_argument("command", nargs="?", help="Command to run")
    parser.add_argument("--port", type=int, default=8765, help="Port for API server")
    parser.add_argument("--regions", type=str, help="Comma-separated list of regions to ingest")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    
    args = parser.parse_args()
    
    if not args.command:
        print("AETHERA v0.2.0 — Sovereign Computational Geometry Platform")
        print("\nUsage:")
        print("  aethera serve [--port PORT]     Start API server")
        print("  aethera ingest [--regions LIST] Run Physical Truth ingestion")
        print("  aethera audit                   Run platform audit")
        print("  aethera version                 Show version")
        return
    
    if args.command == "version":
        from aethera import __version__
        print(f"AETHERA v{__version__}")
    
    elif args.command == "serve":
        print(f"Starting AETHERA API server on port {args.port}...")
        import uvicorn
        from aethera.api import app
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    
    elif args.command == "ingest":
        print(f"Running Physical Truth ingestion for regions: {args.regions}")
        from aethera.ingest.pipeline import run_ingestion
        regions = args.regions.split(",") if args.regions else None
        asyncio.run(run_ingestion(regions=regions, workers=args.workers))
    
    elif args.command == "audit":
        from scripts.audit import audit
        audit()
    
    else:
        print(f"Unknown command: {args.command}")
        print("Use 'aethera --help' for usage information")


if __name__ == "__main__":
    main()
