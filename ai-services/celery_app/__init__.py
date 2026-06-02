"""
Celery application for TWHC async file processing pipeline.

# Last Update: 2026-03-26 20:30:00
# Author: Daniel Chung
# Version: 1.1.0
"""

import os
import sys

# Ensure ai-services/ is on sys.path so that kb_pipeline (and other
# sibling packages) are importable even when Celery spawns fresh
# worker processes (macOS Python ≥3.14 defaults to "spawn").
_AISERVICES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AISERVICES_DIR not in sys.path:
    sys.path.insert(0, _AISERVICES_DIR)
