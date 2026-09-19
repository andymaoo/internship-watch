"""Compatibility entry point for the durable internship_watch pipeline."""
import sys
from internship_watch.cli import main

if __name__ == "__main__":
    main(sys.argv[1:] or ["run"])
