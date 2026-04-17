"""core.vault.base — CredentialVault ABC, VaultAccessLog dataclass y excepciones.

Define la interfaz pública del módulo de vault. Los adaptadores concretos
(e.g. FernetPostgresVault) implementan CredentialVault y usan VaultAccessLog
para registrar cada operación en el audit log.

IMPORTANTE — regla de tamper prevention:
    vault_audit_log es APPEND-ONLY a nivel de aplicación.
    CredentialVault NO expone métodos para actualizar o borrar filas de auditoría.
    Toda escritura en vault_audit_log es exclusivamente un INSERT realizado por
    el propio adaptador después de cada store / get / delete / list_keys.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from core.tenants.base import TenantId


# ---------------------------------------------------------------------------
# Excepciones de dominio
# ---------------------------------------------------------------------------


class SecretNotFound(Exception):
    """Se lanza cuando se solicita una clave que no existe para ese tenant."""


class VaultDecryptError(Exception):
    """Se lanza cuando Fernet no puede descifrar el ciphertext almacenado.

    Causas comunes: master key rotada sin re-cifrar los datos, datos corruptos.
    """


class CrossTenantAccessError(Exception):
    """Se lanza cuando se detecta un intento de acceder a datos de otro tenant.

    En la implementación con FernetPostgresVault la aislación se garantiza a nivel
    de query (WHERE tenant_id = :tenant_id), por lo que esta excepción actúa
    como salvaguarda adicional en capas superiores.
    """


class MasterKeyMissingError(Exception):
    """Se lanza al instanciar el vault si VAULT_MASTER_KEY no está configurada."""


# ---------------------------------------------------------------------------
# Dataclass de log de acceso
# ---------------------------------------------------------------------------


@dataclass
class VaultAccessLog:
    """Registro de una operación sobre el vault.

    Campos:
        tenant_id: UUID del tenant que realizó (o intentó realizar) la operación.
        key_name: Nombre de la clave afectada (nunca el valor).
        action: Tipo de operación — "store", "get", "delete", o "list_keys".
        timestamp: Momento exacto de la operación.
        caller_context: Contexto opcional (e.g. nombre del provider que llamó).
    """

    tenant_id: TenantId
    key_name: str
    action: str  # "store" | "get" | "delete" | "list_keys"
    timestamp: datetime
    caller_context: str | None = field(default=None)


# ---------------------------------------------------------------------------
# ABC — puerto de salida (Hexagonal Architecture)
# ---------------------------------------------------------------------------


class CredentialVault(ABC):
    """Almacén cifrado de secretos por tenant. Todas las operaciones auditan.

    Cada método acepta tenant_id como primer argumento para garantizar el aislamiento
    a nivel de tipo — los adaptadores DEBEN incluir tenant_id en cada query de base
    de datos (WHERE tenant_id = :tenant_id).

    Regla de audit log:
        Cada operación (store, get, delete, list_keys) DEBE escribir un registro
        en vault_audit_log — incluso si la operación falla. Esto garantiza un
        trail forense completo.

    Regla de tamper prevention:
        Esta ABC NO define métodos para actualizar o eliminar filas de audit log.
        Los adaptadores concretos tampoco deben exponerlos. vault_audit_log es
        APPEND-ONLY: solo INSERTs realizados internamente por el adaptador.

    Nota sobre list_keys:
        list_keys() retorna SOLO nombres de claves — NUNCA valores ni ciphertexts.
    """

    @abstractmethod
    async def store(self, tenant_id: TenantId, key_name: str, value: str) -> None:
        """Cifra y persiste un secreto para el tenant.

        Si ya existe una clave con ese nombre para el tenant, hace UPSERT
        (reemplaza el ciphertext anterior). Escribe un registro "store" en
        vault_audit_log.

        Args:
            tenant_id: UUID del tenant propietario del secreto.
            key_name: Nombre lógico de la clave (e.g. "gcal_token").
            value: Valor en texto plano — se cifra antes de persistir.
        """
        ...

    @abstractmethod
    async def get(self, tenant_id: TenantId, key_name: str) -> str:
        """Recupera y descifra un secreto del tenant.

        Escribe un registro "get" en vault_audit_log.

        Args:
            tenant_id: UUID del tenant propietario del secreto.
            key_name: Nombre lógico de la clave.

        Returns:
            Valor en texto plano.

        Raises:
            SecretNotFound: si la clave no existe para ese tenant.
            VaultDecryptError: si el ciphertext no puede ser descifrado.
        """
        ...

    @abstractmethod
    async def delete(self, tenant_id: TenantId, key_name: str) -> None:
        """Elimina físicamente el secreto del tenant.

        Escribe un registro "delete" en vault_audit_log.

        Args:
            tenant_id: UUID del tenant propietario del secreto.
            key_name: Nombre lógico de la clave.

        Raises:
            SecretNotFound: si la clave no existe para ese tenant.
        """
        ...

    @abstractmethod
    async def list_keys(self, tenant_id: TenantId) -> list[str]:
        """Lista los nombres de todas las claves almacenadas para el tenant.

        NUNCA retorna valores ni ciphertexts — solo key_name strings.
        Escribe un registro "list_keys" en vault_audit_log.

        Args:
            tenant_id: UUID del tenant.

        Returns:
            Lista de nombres de claves (puede estar vacía).
        """
        ...
