"""Make the src-layout modules importable the same way pdf_inspector.py does."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "citation_rag"))
