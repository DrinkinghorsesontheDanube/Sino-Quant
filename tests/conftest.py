"""Sandbox-friendly replacement for pytest's ``tmp_path``.

The stock fixture creates numbered directories under the system temp area
with permission hardening, which this locked-down environment rejects with
WinError 5. A plain workspace-local directory with default (inherited)
ACLs works everywhere, so we shadow the built-in fixture by name.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent / ".tmp-scratch"


@pytest.fixture()
def tmp_path() -> Path:
    BASE.mkdir(exist_ok=True)
    path = BASE / uuid.uuid4().hex[:12]
    path.mkdir(parents=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)
