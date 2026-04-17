# Agente de Voz Argentino

Voice agent con acento argentino que responde sobre datos de negocio usando RAG. Pensado para soporte, seguimiento y ventas simples en pymes latinoamericanas. 

Stack optimizado para **Ultra-Baja Latencia (Sub-300ms)**: 
* Orquestación: **LiveKit Agents**
* LLM: **Groq (Llama-3.1-8b-instant)**
* TTS: **Deepgram Aura (ajustado para acento local) / ElevenLabs**
* STT: **Deepgram Nova 3**
* Despliegue: **Railway (US-East)**

El diferenciador crítico es la naturalidad local, la inmediatez cognitiva (E2E delay ~250ms) y el comportamiento conversacional.

---

## 🚀 Arquitectura "Edge-Cloud Dual-Loop"
Para romper la barrera de los 800ms de latencia, el orquestador backend fue migrado de local a un contenedor nativo en Railway (US-East). 
Esto elimina la penalidad de red del "round-trip" entre Sudamérica y las APIs de LLM/TTS ubicadas en USA.

### Métricas de Rendimiento Registradas
Al correr en el mismo eje de datacenter que los proveedores, se obtuvieron latencias de clase mundial:
* **LLM TTFT (Time to First Token):** ~130ms. (Groq API, procesado sobre LPUs).
* **TTS TTFB (Time to First Byte):** ~75ms - ~120ms. (Deepgram Aura Streaming).
* **Latencia Percibida E2E:** **~250ms flat**. (*Desde el momento que el usuario finaliza la frase hasta que escucha la voz de vuelta, sin contar la retención por VAD de 0.5s*).

---

## 🛠️ Despliegue en Railway

El proyecto está dockerizado usando `uv` para builds rápidos en producción.

### Requisitos (Variables de Entorno)
En la plataforma de hosting se deben proveer las siguientes claves:
- `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`
- `GROQ_API_KEY` (Obligatoria para la velocidad ~130ms de LLM)
- `DEEPGRAM_API_KEY` (Para STT/TTS)
- *(Opcional)* `ELEVENLABS_API_KEY` si decides volver a ElevenLabs prestando atención a los cuellos de cuota (Rate Limit) que causan errores `no audio frames pushed`.

*Importante: Railway requiere configurar el `Root Directory` apuntando a `/Voice-Agent`.*

---

## Multi-Tenant Data Access

The agent supports multiple tenants (clinics, businesses) from a single deployment. Each tenant has its own configuration and encrypted secrets, isolated at the database level.

### Architecture

Two independent packages handle tenant data:

- **`core/tenants/`** — tenant registry (CRUD + soft-delete via `status` enum). The `TenantRegistry` ABC is backed by `PostgresTenantRegistry` using SQLAlchemy 2.x async.
- **`core/vault/`** — encrypted credential store. The `CredentialVault` ABC is backed by `FernetPostgresVault`, which encrypts every secret with Fernet (AES-128-CBC + HMAC-SHA256) and appends an append-only audit row on every operation.
- **`core/orchestrator/tenant_context.py`** — `TenantContext` dataclass that binds a loaded `Tenant` to a `CredentialVault` reference. Secrets are fetched lazily on demand — never preloaded.

### Usage Example

```python
import asyncio
from uuid import uuid4
from core.tenants.base import Tenant, TenantId
from core.tenants.postgres import PostgresTenantRegistry
from core.vault.fernet_postgres import FernetPostgresVault
from core.orchestrator.tenant_context import build_tenant_context
from core.db.engine import get_session

async def main() -> None:
    async with get_session() as session:
        registry = PostgresTenantRegistry(session)
        vault = FernetPostgresVault(caller_context="example")

        # Create a tenant
        tenant = await registry.create(
            Tenant(id=TenantId(uuid4()), name="acme", vertical="clinic")
        )

        # Store a secret
        await vault.store(tenant.id, "openai_api_key", "sk-...", session=session)

        # Build context and retrieve secret lazily
        ctx = await build_tenant_context(tenant.id, registry=registry, vault=vault)
        # ctx.get_secret() requires a session — pass it in your provider
        key = await vault.get(tenant.id, "openai_api_key", session=session)
        print(key)  # sk-...

asyncio.run(main())
```

### Feature Flag: `USE_TENANT_REGISTRY`

The tenant registry is **disabled by default** to preserve backward compatibility with YAML-based `load_vertical()` configurations.

| `USE_TENANT_REGISTRY` | Behavior |
|---|---|
| `false` (default) | Existing YAML `load_vertical()` path — no DB dependency |
| `true` | `build_tenant_context_from_env()` loads tenant from Postgres + resolves secrets from vault |

Set this flag in your environment or Railway service variables. See `env.example` for all required variables.

### Required Environment Variables

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/voiceagent
VAULT_MASTER_KEY=<fernet-key>   # generate: uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
USE_TENANT_REGISTRY=false
```

### Running Migrations

```bash
uv run alembic upgrade head   # apply all migrations
uv run alembic downgrade -1   # rollback one step
```

See `docs/runbooks/alembic-migrations.md` for the full runbook including the ENUM gotcha.
For key rotation procedures, see `docs/runbooks/master-key-rotation.md`.

---

## 📚 Workspace

Todo el trabajo del equipo se registra en Notion (teamspace: Agent AI). Ver `.agents/skills/voice-agent-workspace/SKILL.md` para el protocolo completo de cómo y dónde guardar cada tipo de información.
