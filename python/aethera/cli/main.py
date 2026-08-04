"""AETHERA CLI — minimal entry point."""
import sys, json
def main():
    if len(sys.argv) < 2:
        print("AETHERA v0.2.0 — usage: aethera <command>")
        print("Commands: solve, ghost, alien, dynamics")
        return
    cmd = sys.argv[1]
    if cmd == "version":
        from aethera import __version__
        print(__version__)
    else:
        print(f"Unknown command: {cmd}")
