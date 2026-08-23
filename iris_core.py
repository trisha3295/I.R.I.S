"""
I.R.I.S. (Intelligent Real-time Interface System) Core Entrypoint.
Upgraded Ultra-Fast, Zero-Jitter, Anti-Gimbal-Lock Architecture.
"""
import sys
import os

# Ensure current directory is on python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iris_app import main

if __name__ == "__main__":
    main()