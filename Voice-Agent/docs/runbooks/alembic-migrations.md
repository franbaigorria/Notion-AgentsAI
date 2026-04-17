# Runbook: Alembic Migrations

## Prerequisites

- `DATABASE_URL` environment variable set to a `postgresql+asyncpg://` connection string
- `uv` installed (project uses `uv` as package manager)

For local development, Postgres must be running. The project uses Homebrew Postgres
on port **5432** (not Docker port 55432 — Docker is for CI only):

```bash
# Homebrew Postgres (local dev)
DATABASE_URL=postgresql+asyncpg://franciscobaigorria@localhost:5432/voiceagent_test

# Docker Postgres (CI / integration tests)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/voiceagent_test
```

---

## Apply Migrations

Run all pending migrations up to `head`:

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/voiceagent"
uv run alembic upgrade head
```

This command is **idempotent** — running it against an already-current database
is a no-op.

---

## Rollback One Step

```bash
uv run alembic downgrade -1
```

To roll back to a specific revision:

```bash
uv run alembic downgrade 0001_create_tenants_table
```

To roll back everything:

```bash
uv run alembic downgrade base
```

---

## Check Current Revision

```bash
uv run alembic current
```

---

## Create a New Migration

Use `--autogenerate` to diff ORM models against the live schema:

```bash
uv run alembic revision --autogenerate -m "add phone_number to tenants"
```

Always **review the generated file** before applying — autogenerate can miss
some patterns (e.g. server-side defaults, raw SQL indexes, ENUM types).

---

## ENUM Gotcha (CRITICAL)

**Never use `sa.Enum(...)` inline inside `op.create_table()`.**

SQLAlchemy will try to `CREATE TYPE` the ENUM as part of the table DDL, which
fails if the type already exists (e.g. on a second `upgrade head` run or in a
test that creates the schema from scratch).

### Wrong pattern (will break on re-run):

```python
# BAD — sa.Enum() with create_implicit_constraints=True creates the type inline
sa.Column("status", sa.Enum("active", "disabled", name="tenant_status"), ...)
```

### Correct pattern:

```python
from sqlalchemy.dialects import postgresql

# Declare the ENUM once, at module level, with create_type=False
tenant_status_enum = postgresql.ENUM(
    "active",
    "disabled",
    name="tenant_status",
    create_type=False,  # we manage the type manually below
)

def upgrade() -> None:
    # Create the ENUM type explicitly and idempotently
    tenant_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenants",
        # ...
        sa.Column("status", tenant_status_enum, nullable=False, server_default="active"),
        # ...
    )

def downgrade() -> None:
    op.drop_table("tenants")
    tenant_status_enum.drop(op.get_bind(), checkfirst=True)
```

Key rules:
1. Use `postgresql.ENUM(..., create_type=False)` — never `sa.Enum(...)` for named types
2. Declare the enum variable **once** at module level and reuse it in both `upgrade()` and `downgrade()`
3. Always call `.create(op.get_bind(), checkfirst=True)` explicitly in `upgrade()`
4. Always call `.drop(op.get_bind(), checkfirst=True)` explicitly in `downgrade()`

See `alembic/versions/0001_create_tenants_table.py` for a working example.

---

## Migration File Location

All migration files live in `alembic/versions/`. The naming convention is:

```
{revision_id}_{short_description}.py
```

Current migrations:
- `0001_create_tenants_table.py` — creates `tenants` table + `tenant_status` ENUM
- `0002_create_tenant_secrets_audit.py` — creates `tenant_secrets` + `vault_audit_log` tables
