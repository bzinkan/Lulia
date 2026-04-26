"""Pytest config — make `from src.lms_agents...` resolvable when invoking
pytest from the project root inside the API container.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
