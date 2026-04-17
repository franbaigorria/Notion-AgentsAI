"""core.orchestrator.tenant_context — TenantContext dataclass y factory.

TenantContext encapsula el Tenant cargado y un CredentialVault reference
para acceso lazy a secretos durante la sesión de voz.

DECISIÓN DE DISEÑO — Task 4.1 (Investigación):
    Fuente de tenant_id: ctx.job.metadata (JSON con clave "tenant_id")

    Se eligió ctx.job.metadata sobre ctx.room.metadata por las siguientes razones:

    1. Disponibilidad: ctx.job.metadata está disponible ANTES de ctx.connect().
       Esto permite fallar rápido (TenantNotFound / TenantDisabled) sin desperdiciar
       una conexión WebRTC al servidor LiveKit.

    2. Origen controlado: job.metadata es seteado por el backend cuando hace el
       job dispatch (livekit.api.RoomServiceClient.create_room o AgentDispatchClient).
       room.metadata puede ser modificado por cualquier participante de la sala.

    3. Semántica: el tenant_id es metadata del JOB (quién pidió el agente), no
       metadata de la SALA (qué hay en la sala). Job metadata es el lugar correcto.

    Formato esperado: JSON string con clave "tenant_id" (UUID string).
    Ejemplo: '{"tenant_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}'

    TODO (fuentes alternativas a implementar según necesidad):
        - ctx.room.metadata (post-connect): útil si el backend no puede escribir
          job metadata directamente (e.g. frontend-driven rooms).
        - SIP headers (X-Tenant-Id): necesario para llamadas de telefonía vía
          SIP trunk de LiveKit. Requiere parsear ctx.room.participants para
          encontrar el SIP participant y leer sus atributos.

Uso::

    from core.orchestrator.tenant_context import TenantContext, build_tenant_context

    tenant_ctx = await build_tenant_context(
        tenant_id=tenant_id,
        registry=registry,
        vault=vault,
    )
    secret = await tenant_ctx.get_secret("openai_api_key")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.tenants.base import Tenant, TenantId
from core.vault.base import CredentialVault

if TYPE_CHECKING:
    from core.tenants.base import TenantRegistry


# ---------------------------------------------------------------------------
# TenantContext — dataclass de dominio (frozen, inmutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TenantContext:
    """Contexto de tenant para una sesión de voz.

    Encapsula el Tenant cargado desde el registry y una referencia al
    CredentialVault. Los secretos se acceden de forma lazy via get_secret()
    — NO se precargan todos los secretos al inicio de la sesión.

    Args:
        tenant: Dataclass Tenant con la configuración del tenant activo.
        vault: Referencia al CredentialVault. No se llama al construir —
               solo cuando un provider necesita un secreto específico.

    Inmutabilidad (frozen=True):
        Los campos no pueden ser reasignados después de la construcción.
        Esto garantiza que el contexto de tenant no sea mutado durante la sesión.
    """

    tenant: Tenant
    vault: CredentialVault

    async def get_secret(self, key_name: str) -> str:
        """Recupera un secreto del vault para este tenant (acceso lazy).

        El vault NO es llamado al construir TenantContext — solo cuando
        un provider llama explícitamente a get_secret().

        Args:
            key_name: Nombre lógico del secreto (e.g. "openai_api_key").

        Returns:
            Valor en texto plano del secreto.

        Raises:
            SecretNotFound: si la clave no existe para este tenant.
            VaultDecryptError: si el ciphertext no puede ser descifrado.
        """
        return await self.vault.get(self.tenant.id, key_name)


# ---------------------------------------------------------------------------
# Factory — build_tenant_context()
# ---------------------------------------------------------------------------


async def build_tenant_context(
    tenant_id: TenantId,
    *,
    registry: "TenantRegistry",
    vault: CredentialVault,
) -> TenantContext:
    """Carga el Tenant desde el registry y construye un TenantContext.

    Esta función es el punto de entrada para el path con USE_TENANT_REGISTRY=true.
    Se llama al inicio de cada sesión de voz, antes de construir los providers.

    El vault NO se consulta aquí — es inyectado como referencia para acceso lazy
    posterior via TenantContext.get_secret().

    Args:
        tenant_id: UUID del tenant extraído de ctx.job.metadata.
        registry: Implementación de TenantRegistry (tipicamente PostgresTenantRegistry).
        vault: Implementación de CredentialVault (tipicamente FernetPostgresVault).

    Returns:
        TenantContext con el tenant cargado y el vault referenciado.

    Raises:
        TenantNotFound: si tenant_id no existe en el registry. NO se silencia.
        TenantDisabled: si el tenant existe pero está disabled. NO se silencia.
    """
    tenant = await registry.get(tenant_id)
    return TenantContext(tenant=tenant, vault=vault)
