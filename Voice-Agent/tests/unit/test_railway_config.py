"""Railway config guardrails for the thin-tenant MVP.

The MVP runtime does not require Postgres. Migrations belong to the future
multi-tenant path, so railway.json must not run Alembic on every deploy by default.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_railway_deploy_does_not_run_db_migrations_by_default() -> None:
    config = json.loads(Path("railway.json").read_text())

    deploy_config = config.get("deploy", {})

    assert "preDeployCommand" not in deploy_config
