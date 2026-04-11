import sys
import os

# Add campaign-analyzer/ to Python path so its modules are importable
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "campaign-analyzer"))

from app import app  # noqa: E402 — must come after sys.path setup
