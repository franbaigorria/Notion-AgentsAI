from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class TelephonyProvider(ABC):
    """Interfaz base para la capa de entrada/salida de audio.

    El pipeline no sabe si está en producción (Twilio/LiveKit) o en modo local.
    Esta abstracción es lo que hace posible testear sin telefonía real (RQ-05).
    """

    @abstractmethod
    async def receive_audio(self) -> AsyncIterator[bytes]: ...

    @abstractmethod
    async def send_audio(self, audio: AsyncIterator[bytes]) -> None: ...

    @abstractmethod
    def get_caller_id(self) -> str: ...
