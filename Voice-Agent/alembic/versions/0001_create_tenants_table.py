"""create tenants table

Revision ID: 0001_create_tenants_table
Revises:
Create Date: 2026-04-16

Creates the `tenants` table with all columns defined in TenantORM:
  - id UUID PK
  - name TEXT UNIQUE NOT NULL
  - vertical TEXT NOT NULL
  - config JSONB NOT NULL DEFAULT '{}'
  - status ENUM('active','disabled') NOT NULL DEFAULT 'active'
  - created_at / updated_at TIMESTAMPTZ
  - deleted_at TIMESTAMPTZ NULL

Also creates composite index ix_tenants_vertical_status used by list(vertical=...).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_create_tenants_table"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Enum definition — must be created/dropped explicitly in Postgres
# ---------------------------------------------------------------------------

tenant_status_enum = postgresql.ENUM(
    "active",
    "disabled",
    name="tenant_status",
    create_type=False,  # we manage it manually below
)


def upgrade() -> None:
    """Create tenants table and supporting index."""
    # Create ENUM type first
    tenant_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("vertical", sa.Text(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "status",
            tenant_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_tenants_name"),
    )

    # Composite index for list(vertical=...) queries
    op.create_index(
        "ix_tenants_vertical_status",
        "tenants",
        ["vertical", "status"],
    )


def downgrade() -> None:
    """Drop tenants table and ENUM type."""
    op.drop_index("ix_tenants_vertical_status", table_name="tenants")
    op.drop_table("tenants")
    tenant_status_enum.drop(op.get_bind(), checkfirst=True)
