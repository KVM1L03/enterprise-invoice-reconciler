"""Single source of truth for filesystem paths.

Local dev: paths resolve under the repo root (PROJECT_ROOT).
Cloud (Railway / any container with a mounted volume): set ``DATA_DIR``
to the volume mount (e.g. ``/app/data``) and every persistent artefact —
the SQLite ERP, invoice PDFs, approved/discrepancy archives — lives on
the volume so container restarts don't wipe demo sessions.

Why one module:
- Lots of services (api_gateway, ai_worker, mcp_bridge, seed scripts)
  used to recompute these paths independently with
  ``Path(__file__).resolve().parent.parent / "mock_data"``. That works
  for repo-root execution but breaks under Railway where the CWD and
  source layout differ. One env-driven module fixes it everywhere.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root — works for `uv run`, pytest, and the Docker image where the
# project is copied to /app. ``parents[1]`` resolves to `<repo>/`.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

# DATA_DIR is the volume mount in production, the repo root in dev.
# Keep it as Path so callers can do `DATA_DIR / "subdir"` directly.
DATA_DIR: Path = Path(os.environ.get("DATA_DIR", str(PROJECT_ROOT)))

# SQLite ERP database — persisted across restarts when DATA_DIR is a
# mounted volume. The mcp_bridge subdir is kept so a single DATA_DIR
# can also host future per-service state alongside the DB.
ERP_DB_PATH: Path = DATA_DIR / "mcp_bridge" / "erp_mock.db"

# Invoice file routing tree
MOCK_DATA_DIR: Path = DATA_DIR / "mock_data"
INVOICES_DIR: Path = MOCK_DATA_DIR / "invoices"
APPROVED_DIR: Path = MOCK_DATA_DIR / "approved"
DISCREPANCY_DIR: Path = MOCK_DATA_DIR / "discrepancy"


def ensure_data_dirs() -> None:
    """Create the volume's directory layout. Idempotent; safe at every startup."""
    ERP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    for d in (INVOICES_DIR, APPROVED_DIR, DISCREPANCY_DIR):
        d.mkdir(parents=True, exist_ok=True)
