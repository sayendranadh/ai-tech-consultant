"""Global test configuration for Task 1.

Forces KB_QA_CLIENT=mock for the entire test session unless PYTEST_LIVE=1.
Tests must not depend on the shell environment for this setting.
"""
import os
import sys
from pathlib import Path

# Force mock QA client unless explicitly opted into live mode.
if os.environ.get("PYTEST_LIVE", "0") != "1":
    os.environ["KB_QA_CLIENT"] = "mock"

# Ensure repo root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
