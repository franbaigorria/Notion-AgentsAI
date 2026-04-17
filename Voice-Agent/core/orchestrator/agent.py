"""Shared builders — Voice Agent Platform.

Funciones compartidas para cargar configuración del vertical y construir
los componentes (STT, LLM, TTS, Realtime) que usan los agentes en apps/.

Los entry points están en:
    apps/pipeline/agent.py   — STT → LLM → TTS
    apps/realtime/agent.py   — OpenAI Speech-to-Speech
    apps/launcher.py         — Despacha según AGENT_MODE

Variables de entorno requeridas:
    VERTICAL            nombre del directorio en verticals/ (default: clinica)
    LIVEKIT_URL         URL del servidor LiveKit
    LIVEKIT_API_KEY     API key de LiveKit
    LIVEKIT_API_SECRET  API secret de LiveKit

Variables de entorno opcionales:
    USE_TENANT_REGISTRY  Si es exactamente "true", activa el path multi-tenant.
                         Cualquier otro valor (incluido ausente) mantiene el
                         comportamiento YAML-based original (default: OFF).
                         Cuando está ON, se requieren DATABASE_URL y VAULT_MASTER_KEY.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from dotenv import load_dotenv

if TYPE_CHECKING:
    from core.tenants.base import TenantId, TenantRegistry
    from core.vault.base import CredentialVault
    from core.orchestrator.tenant_context import TenantContext


load_dotenv()

VERTICALS_DIR = Path(__file__).parent.parent.parent / "verticals"


def load_vertical(name: str) -> dict:
    """Carga config.yaml y persona.md del vertical indicado."""
    path = VERTICALS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Vertical '{name}' no encontrado en {VERTICALS_DIR}")

    with open(path / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with open(path / "persona.md", encoding="utf-8") as f:
        config["persona"] = f.read()

    return config


def build_stt(config: dict):
    from core.stt.deepgram import DeepgramSTT
    from core.stt.elevenlabs_stt import ElevenLabsSTT
    from core.stt.openai_stt import OpenAISTT

    providers = {
        "deepgram": lambda: DeepgramSTT(
            model=config.get("stt_model", "nova-3"),
            language=config.get("language", "es"),
        ),
        "elevenlabs": lambda: ElevenLabsSTT(
            model=config.get("stt_model", "scribe_v2_realtime"),
            language=config.get("language", "es"),
        ),
        "openai": lambda: OpenAISTT(
            model=config.get("stt_model", "gpt-4o-mini-transcribe"),
            language=config.get("language", "es"),
            use_realtime=config.get("stt_use_realtime", True),
        ),
    }

    name = config.get("stt_provider", "deepgram")
    if name not in providers:
        raise ValueError(f"STT provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


def is_realtime_mode(config: dict) -> bool:
    """True si el modo es realtime (speech-to-speech, bypassea STT+TTS)."""
    return config.get("mode", "pipeline") == "realtime"


def build_realtime_llm(config: dict):
    """Construye el modelo Realtime speech-to-speech de OpenAI."""
    from core.llm.openai_realtime import OpenAIRealtime

    realtime_cfg = config.get("realtime", {})
    return OpenAIRealtime(
        model=realtime_cfg.get("model", "gpt-4o-mini-realtime-preview"),
        voice=realtime_cfg.get("voice", "ash"),
        temperature=realtime_cfg.get("temperature"),
        speed=realtime_cfg.get("speed"),
    ).as_livekit_plugin()


def build_llm(config: dict):
    from core.llm.claude import ClaudeLLM
    from core.llm.gemini import GeminiLLM
    from core.llm.groq import GroqLLM
    from core.llm.ollama import OllamaLLM
    from core.llm.openai import OpenAILLM

    providers = {
        "claude": lambda: ClaudeLLM(model=config.get("llm_model", "claude-sonnet-4-6")),
        "openai": lambda: OpenAILLM(model=config.get("llm_model", "gpt-4o-mini")),
        "ollama": lambda: OllamaLLM(model=config.get("llm_model", "gemma4:e4b")),
        "groq": lambda: GroqLLM(model=config.get("llm_model", "llama-3.1-8b-instant")),
        "gemini": lambda: GeminiLLM(model=config.get("llm_model", "gemini-3.1-flash-lite")),
    }

    name = config.get("llm_provider", "claude")
    if name not in providers:
        raise ValueError(f"LLM provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


def build_tts(config: dict):
    from core.tts.deepgram import DeepgramTTS
    from core.tts.elevenlabs import ElevenLabsTTS
    from core.tts.cartesia import CartesiaTTS
    from core.tts.fish_speech import FishSpeechTTS
    from core.tts.gemini_tts import GeminiTTS
    from core.tts.openai_tts import OpenAITTS

    voice_settings = config.get("voice_settings", {})
    providers = {
        "elevenlabs": lambda: ElevenLabsTTS(
            voice_id=os.environ.get("ELEVENLABS_VOICE_ID") or config.get("voice_id", ""),
            model=config.get("tts_model", "eleven_multilingual_v2"),
            stability=voice_settings.get("stability"),
            similarity_boost=voice_settings.get("similarity_boost"),
            style=voice_settings.get("style"),
            speed=voice_settings.get("speed"),
            apply_text_normalization=config.get("apply_text_normalization", "auto"),
        ),
        "deepgram": lambda: DeepgramTTS(
            model=config.get("tts_model", "aura-2-antonia-es"),
        ),
        "cartesia": lambda: CartesiaTTS(
            voice_id=os.environ.get("CARTESIA_VOICE_ID") or config.get("voice_id", ""),
            model=config.get("tts_model", "sonic-multilingual"),
        ),
        "fish_speech": lambda: FishSpeechTTS(
            voice_id=os.environ.get("FISH_AUDIO_VOICE_ID") or config.get("voice_id", ""),
            model=config.get("tts_model", ""),
        ),
        "openai": lambda: OpenAITTS(
            voice=config.get("voice_id", "ash"),
            model=config.get("tts_model", "gpt-4o-mini-tts"),
            instructions=config.get("tts_instructions"),
            speed=voice_settings.get("speed", 1.0),
        ),
        "gemini": lambda: GeminiTTS(
            voice=config.get("voice_id", "Charon"),
            model=config.get("tts_model", "gemini-3.1-flash-tts-preview"),
            instructions=config.get("tts_instructions"),
        ),
    }

    name = config.get("tts_provider", "elevenlabs")
    if name not in providers:
        raise ValueError(f"TTS provider desconocido: '{name}'. Disponibles: {list(providers)}")

    return providers[name]().as_livekit_plugin()


# ---------------------------------------------------------------------------
# Multi-tenant path — feature flag USE_TENANT_REGISTRY
# ---------------------------------------------------------------------------


def _tenant_registry_enabled() -> bool:
    """Retorna True solo si USE_TENANT_REGISTRY es exactamente 'true' (case-sensitive)."""
    return os.environ.get("USE_TENANT_REGISTRY", "").strip() == "true"


async def build_tenant_context_from_env(
    tenant_id: "TenantId",
    *,
    registry: "TenantRegistry | None" = None,
    vault: "CredentialVault | None" = None,
) -> "TenantContext | None":
    """Construye un TenantContext si USE_TENANT_REGISTRY=true, o retorna None.

    Punto de entrada para el path multi-tenant en los agentes (apps/pipeline/agent.py,
    apps/realtime/agent.py). Encapsula la lógica del feature flag para que los
    agentes no necesiten conocer la variable de entorno directamente.

    Comportamiento por flag:
        - USE_TENANT_REGISTRY != "true" (default, OFF):
            Retorna None. El agente debe continuar con load_vertical() + YAML config.
            SIN llamadas a Postgres, sin imports de SQLAlchemy — idéntico al estado
            anterior a este cambio.

        - USE_TENANT_REGISTRY = "true" (ON):
            Llama a registry.get(tenant_id). Si el tenant existe y está activo,
            retorna un TenantContext con acceso lazy al vault.
            NO silencia TenantNotFound ni TenantDisabled — ambas se propagan
            para que el llamador las maneje (rechazar la sesión).

    Fuente de tenant_id (Task 4.1 — investigación completada):
        Se extrae de ctx.job.metadata (JSON, clave "tenant_id") ANTES de ctx.connect().
        Ver core/orchestrator/tenant_context.py para la decisión completa y TODOs.

    Session management:
        The vault manages its own sessions internally via its session_factory.
        The registry still requires a session at construction time — the caller
        is responsible for providing a session-bound registry (or using the default
        production path which constructs one internally via get_session).

    Args:
        tenant_id: UUID del tenant. Se obtiene de ctx.job.metadata en el agente.
        registry: Implementación de TenantRegistry (p.ej. PostgresTenantRegistry).
                  If None, a PostgresTenantRegistry is constructed with a fresh session.
        vault: Implementación de CredentialVault (p.ej. FernetPostgresVault).
               If None, a FernetPostgresVault() is constructed (uses env vars).

    Returns:
        TenantContext si el flag está activo y el tenant existe.
        None si el flag está inactivo — el agente debe usar el path YAML.

    Raises:
        TenantNotFound: si flag ON y tenant_id no existe. NO se silencia.
        TenantDisabled: si flag ON y el tenant está disabled. NO se silencia.
    """
    if not _tenant_registry_enabled():
        return None

    from core.orchestrator.tenant_context import build_tenant_context

    if vault is None:
        from core.vault.fernet_postgres import FernetPostgresVault

        vault = FernetPostgresVault()

    if registry is not None:
        return await build_tenant_context(tenant_id, registry=registry, vault=vault)

    # Default production path: open a session for registry lookup only.
    # The vault manages its own sessions independently.
    from core.db.engine import get_session
    from core.tenants.postgres import PostgresTenantRegistry

    async with get_session() as session:
        pg_registry = PostgresTenantRegistry(session=session)
        return await build_tenant_context(tenant_id, registry=pg_registry, vault=vault)

