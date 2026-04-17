"""Realtime Agent — OpenAI Speech-to-Speech.

Un único modelo (gpt-4o-mini-realtime) que reemplaza STT + LLM + TTS.
No requiere VAD, STT ni TTS — todo corre dentro del WebSocket de OpenAI.

Multi-tenant (opcional):
    Si USE_TENANT_REGISTRY=true, extrae tenant_id de ctx.job.metadata (JSON,
    clave "tenant_id") ANTES de ctx.connect(). Carga el Tenant desde Postgres
    y construye un TenantContext con acceso lazy al vault de credenciales.
    Si el flag está desactivado (default), usa el path YAML original sin cambios.

    Fuente de tenant_id: ctx.job.metadata
    Razón: disponible antes de connect(); set by server at job dispatch.
    Ver core/orchestrator/tenant_context.py para la decisión completa.

Uso directo (dev):
    AGENT_MODE=realtime uv run python -m apps.realtime.agent dev

En producción se levanta via apps.launcher.
"""

from __future__ import annotations

import json
import logging
import os

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.metrics import log_metrics

from core.orchestrator.agent import build_realtime_llm, load_vertical

logger = logging.getLogger(__name__)


def _extract_tenant_id_from_job(ctx: JobContext):
    """Extrae el tenant_id de ctx.job.metadata (JSON string).

    Formato esperado: '{"tenant_id": "<uuid>"}'

    Returns:
        TenantId si el campo existe y es un UUID válido.
        None si job.metadata está vacío, no es JSON, o no tiene "tenant_id".
    """
    from uuid import UUID
    from core.tenants.base import TenantId

    raw = ctx.job.metadata
    if not raw:
        return None
    try:
        data = json.loads(raw)
        tid_str = data.get("tenant_id")
        if not tid_str:
            return None
        return TenantId(UUID(str(tid_str)))
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("[realtime] job.metadata no es JSON válido o tenant_id inválido: %r", raw)
        return None


async def entrypoint(ctx: JobContext) -> None:
    vertical_name = os.environ.get("VERTICAL", "clinica")
    config = load_vertical(vertical_name)

    # ---------------------------------------------------------------------------
    # Multi-tenant hook (USE_TENANT_REGISTRY=true activates this path)
    # When flag is OFF (default), this block is a no-op and the YAML flow continues.
    # ---------------------------------------------------------------------------
    tenant_ctx = None
    tenant_id = _extract_tenant_id_from_job(ctx)

    if tenant_id is not None:
        from core.orchestrator.agent import build_tenant_context_from_env
        from core.tenants.postgres import PostgresTenantRegistry
        from core.vault.fernet_postgres import FernetPostgresVault
        from core.db.engine import get_session

        vault = FernetPostgresVault(caller_context="realtime_agent")
        async with get_session() as session:
            registry = PostgresTenantRegistry(session=session)
            tenant_ctx = await build_tenant_context_from_env(
                tenant_id=tenant_id,
                registry=registry,
                vault=vault,
            )

    if tenant_ctx is not None:
        logger.info(
            "[realtime] multi-tenant mode: tenant=%s vertical=%s",
            tenant_ctx.tenant.id,
            tenant_ctx.tenant.vertical,
        )
    else:
        logger.debug("[realtime] YAML mode (USE_TENANT_REGISTRY not active or no tenant_id)")

    rt = config.get("realtime", {})
    print(f"[MODE=realtime] model={rt.get('model')} voice={rt.get('voice')}")

    await ctx.connect()

    session = AgentSession(llm=build_realtime_llm(config))

    session.on("metrics_collected", lambda ev: log_metrics(ev.metrics))

    await session.start(
        agent=Agent(instructions=config["persona"]),
        room=ctx.room,
    )

    await session.generate_reply(
        instructions=config.get(
            "greeting",
            "Saludá al usuario con calidez y preguntale en qué podés ayudarlo.",
        )
    )


def main():
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
