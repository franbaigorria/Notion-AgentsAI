import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


# ─── Tone tag utilities ────────────────────────────────────────────────────────

_TONE_TAG_RE = re.compile(r'<tone:\w+>\s*')


def strip_tone_tags(text: str) -> str:
    """Elimina todos los marcadores <tone:X> del texto.

    Usado por proveedores que no soportan control de tono inline
    (ElevenLabs, Cartesia, Deepgram).
    """
    return _TONE_TAG_RE.sub('', text).strip()


# ─── LiveKit preprocessing wrapper ────────────────────────────────────────────

def _make_preprocessed_tts(inner, preprocess_fn):
    """Envuelve cualquier livekit.tts.TTS para preprocesar el texto antes de synthesize().

    Retorna una instancia anónima que intercepta synthesize(), aplica preprocess_fn,
    y delega al plugin original. Así los providers que usan plugins oficiales de LiveKit
    (ElevenLabs, Cartesia, Deepgram) también filtran los <tone:X> tags.
    """
    from livekit.agents import tts as lk_tts

    class _PreprocessedTTS(lk_tts.TTS):
        def __init__(self):
            super().__init__(
                capabilities=inner.capabilities,
                sample_rate=inner.sample_rate,
                num_channels=inner.num_channels,
            )

        def synthesize(self, text: str, *, conn_options=None, **kwargs):
            return inner.synthesize(
                preprocess_fn(text),
                conn_options=conn_options,
                **kwargs,
            )

    return _PreprocessedTTS()


# ─── Base class ───────────────────────────────────────────────────────────────

@dataclass
class TTSResult:
    latency_ms: float
    cost_usd: float
    provider: str


class TTSProvider(ABC):
    """Interfaz base para proveedores de Text-to-Speech.

    Devuelve un stream de audio — no espera a que esté completo (RQ-01).
    Reporta latencia y costo por síntesis (RQ-03, RQ-04).
    """

    @abstractmethod
    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[bytes]: ...

    @abstractmethod
    def as_livekit_plugin(self): ...
