import os
import sys

# Make the project root importable (api/index.py is one level below root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from temporalos.api.main import app  # noqa: E402
