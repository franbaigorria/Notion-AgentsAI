import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


# ─── Tone tag utilities ────────────────────────────────────────────────────────

_TONE_TAG_RE = re.compile(r'</?tone:\w+>\s*')


def strip_tone_tags(text: str) -> str:
    """Elimina todos los marcadores <tone:X> del texto.

    Usado por proveedores que no soportan control de tono inline
    (ElevenLabs, Cartesia, Deepgram).
    """
    return _TONE_TAG_RE.sub('', text).strip()


# ─── LiveKit preprocessing wrapper ────────────────────────────────────────────

def _make_preprocessed_tts(inner, preprocess_fn):
    """Envuelve cualquier livekit.tts.TTS para preprocesar el texto antes de synthesize()
    y stream().

    Intercepta tanto synthesize() (síntesis batch) como stream() (síntesis token-a-token)
    aplicando preprocess_fn al texto antes de delegarlo al plugin original.
    """
    from livekit.agents import tts as lk_tts
    from livekit.agents import DEFAULT_API_CONNECT_OPTIONS

    class _PreprocessedSynthesizeStream:
        """Proxy de SynthesizeStream que preprocesa el texto en push_text()."""

        def __init__(self, inner_stream):
            self._inner = inner_stream

        def push_text(self, token: str) -> None:
            self._inner.push_text(preprocess_fn(token))

        def flush(self) -> None:
            self._inner.flush()

        def end_input(self) -> None:
            self._inner.end_input()

        async def aclose(self) -> None:
            await self._inner.aclose()

        def __aiter__(self):
            return self._inner.__aiter__()

        async def __aenter__(self):
            await self._inner.__aenter__()
            return self

        async def __aexit__(self, *args):
            return await self._inner.__aexit__(*args)

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
                conn_options=conn_options or DEFAULT_API_CONNECT_OPTIONS,
                **kwargs,
            )

        def stream(self, *, conn_options=None, **kwargs):
            return _PreprocessedSynthesizeStream(
                inner.stream(
                    conn_options=conn_options or DEFAULT_API_CONNECT_OPTIONS,
                    **kwargs,
                )
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
