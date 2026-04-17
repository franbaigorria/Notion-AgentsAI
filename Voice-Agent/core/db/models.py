"""SQLAlchemy 2.x ORM models for the tenant-registry-vault feature.

Phase 1: DeclarativeBase + ORM class stubs.
Column bodies are intentionally minimal — full columns are added in
Alembic revisions 0001 (tenants) and 0002 (tenant_secrets + vault_audit_log).
"""

import uuid

from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, LargeBinary, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models in this project."""


class TenantORM(Base):
    """Maps to the `tenants` table.

    Columns are fully specified here so SQLAlchemy can generate accurate
    ``CREATE TABLE`` statements for Alembic autogenerate comparison.
    """

    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, unique=True)
    vertical = Column(Text, nullable=False)
    config = Column(JSONB, nullable=False, server_default="{}")
    status = Column(
        Enum("active", "disabled", name="tenant_status"),
        nullable=False,
        server_default="active",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships (populated in Phase 2/3)
    secrets = relationship("TenantSecretORM", back_populates="tenant", lazy="noload")


class TenantSecretORM(Base):
    """Maps to the `tenant_secrets` table.

    Stores Fernet-encrypted ciphertext per (tenant_id, key_name) pair.
    UNIQUE constraint on (tenant_id, key_name) enables upsert via ON CONFLICT.
    """

    __tablename__ = "tenant_secrets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    key_name = Column(Text, nullable=False)
    ciphertext = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    rotated_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("TenantORM", back_populates="secrets")


class VaultAuditLogORM(Base):
    """Maps to the `vault_audit_log` table.

    Append-only forensic trail. The application MUST NOT expose UPDATE or DELETE
    on this table. Every store / get / delete / list_keys vault operation writes one row.
    Tenant_id is intentionally NOT a FK so audit rows survive tenant deletion.

    action uses TEXT + CHECK constraint instead of a Postgres ENUM type to avoid
    DDL complexity on migration and to allow new action types without a schema migration.
    Valid values: 'store', 'get', 'delete', 'list_keys'.
    """

    __tablename__ = "vault_audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)  # no FK — append-only
    key_name = Column(Text, nullable=True)
    action = Column(Text, nullable=False)  # 'store' | 'get' | 'delete' | 'list_keys'
    caller_context = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
