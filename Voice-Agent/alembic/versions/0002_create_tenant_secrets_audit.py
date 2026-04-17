"""create tenant_secrets and vault_audit_log tables

Revision ID: 0002_create_tenant_secrets_audit
Revises: 0001_create_tenants_table
Create Date: 2026-04-16

Creates two tables:

`tenant_secrets`
  - id UUID PK
  - tenant_id UUID FK→tenants(id) ON DELETE CASCADE
  - key_name TEXT NOT NULL
  - ciphertext BYTEA NOT NULL  (Fernet-encrypted value)
  - created_at TIMESTAMPTZ NOT NULL
  - rotated_at TIMESTAMPTZ NULL  (set on upsert)
  - UNIQUE (tenant_id, key_name)

`vault_audit_log`
  - id BIGSERIAL PK
  - tenant_id UUID NOT NULL  (intentionally NO FK — survives tenant deletion)
  - key_name TEXT NULL
  - action TEXT NOT NULL  (CHECK: 'store' | 'get' | 'delete' | 'list_keys')
  - caller_context TEXT NULL
  - timestamp TIMESTAMPTZ DEFAULT now()
  - INDEX ix_audit_tenant_time (tenant_id, timestamp DESC)

Design note on action column:
  Using TEXT + CHECK constraint instead of a Postgres ENUM type.
  Rationale: avoids DDL gymnastics (no create_type/drop_type needed),
  and allows adding new action types later without a schema migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_create_tenant_secrets_audit"
down_revision: Union[str, Sequence[str], None] = "0001_create_tenants_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tenant_secrets and vault_audit_log tables."""

    # ------------------------------------------------------------------
    # tenant_secrets
    # ------------------------------------------------------------------
    op.create_table(
        "tenant_secrets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key_name", sa.Text(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "key_name", name="uq_tenant_secrets_tenant_key"),
    )

    # Index on tenant_id (queries always filter by it)
    op.create_index(
        "ix_tenant_secrets_tenant_id",
        "tenant_secrets",
        ["tenant_id"],
    )

    # ------------------------------------------------------------------
    # vault_audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "vault_audit_log",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_name", sa.Text(), nullable=True),
        sa.Column(
            "action",
            sa.Text(),
            sa.CheckConstraint(
                "action IN ('store', 'get', 'delete', 'list_keys')",
                name="ck_vault_audit_log_action",
            ),
            nullable=False,
        ),
        sa.Column("caller_context", sa.Text(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Index for forensic queries: tenant audit trail ordered by time
    # Use raw SQL because op.create_index doesn't support DESC order expressions cleanly
    op.execute(
        "CREATE INDEX ix_audit_tenant_time ON vault_audit_log (tenant_id, timestamp DESC)"
    )


def downgrade() -> None:
    """Drop vault_audit_log and tenant_secrets tables."""
    op.execute("DROP INDEX IF EXISTS ix_audit_tenant_time")
    op.drop_table("vault_audit_log")

    op.drop_index("ix_tenant_secrets_tenant_id", table_name="tenant_secrets")
    op.drop_table("tenant_secrets")
