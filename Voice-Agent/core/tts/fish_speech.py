"""Fish Audio TTS — wrapper para LiveKit Agents 1.5.x.

Consume el endpoint REST /v1/tts de Fish Audio y emite audio
a través del AudioEmitter de LiveKit (contrato ChunkedStream._run).

Uso:
    tts = FishSpeechTTS(voice_id="...", model="s1")
    session = AgentSession(tts=tts, ...)
"""

import os
import re
import logging

import httpx
from livekit.agents import tts, utils

from .base import TTSProvider

logger = logging.getLogger(__name__)

# Mapeo vocabulario neutral → Fish Audio S2 Pro inline tags
# Tags verificados contra la lista oficial de S2 Pro.
# S2 Pro también acepta free-form ("speaking with warmth") pero usamos los canónicos.
_TONE_MAP: dict[str, str] = {
    "excited":      "[excited]",
    "empathetic":   "[low voice]",   # cálido y cercano
    "soft":         "[low volume]",  # suave/tranquilizador
    "pause":        "[short pause]", # más natural en conversación que [pause]
    "cheerful":     "[laughing]",    # tag oficial (no [laugh])
    "professional": "",              # tono default — sin tag
    "serious":      "",              # ídem
}

_TONE_TAG_RE = re.compile(r'<tone:(\w+)>\s*')


class FishSpeechTTS(TTSProvider, tts.TTS):
    def __init__(self, voice_id: str = "", model: str = "s2-pro"):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=44100,
            num_channels=1,
        )
        self.voice_id = voice_id
        self.model_name = model
        self.api_url = os.environ.get("FISH_AUDIO_URL", "https://api.fish.audio/v1/tts")
        self.api_key = os.environ.get("FISH_AUDIO_API_KEY", "")

    def preprocess_text(self, text: str) -> str:
        """Mapea <tone:X> → Fish Audio inline tags. Tags desconocidos se eliminan."""
        def replace(m: re.Match) -> str:
            return _TONE_MAP.get(m.group(1), "")
        return _TONE_TAG_RE.sub(replace, text).strip()

    def synthesize(  # type: ignore[override]
        self, text: str, *, conn_options=None, **kwargs
    ) -> "tts.ChunkedStream":
        # Satisface TTSProvider (ABC) y livekit.tts.TTS al mismo tiempo.
        # La firma difiere de TTSProvider.synthesize — por eso type: ignore[override].
        return _FishChunkedStream(
            tts=self,
            input_text=self.preprocess_text(text),
            conn_options=conn_options or tts.DEFAULT_API_CONNECT_OPTIONS,
        )

    def as_livekit_plugin(self) -> "tts.TTS":
        """Devuelve self — FishSpeechTTS ya hereda de livekit.tts.TTS."""
        return self


class _FishChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: FishSpeechTTS,
        input_text: str,
        conn_options,
    ):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)

    async def _run(self, output_emitter) -> None:
        """Contrato LiveKit 1.5.x: recibe un AudioEmitter, le pushea bytes crudos."""
        fish_tts: FishSpeechTTS = self._tts  # type: ignore[assignment]

        headers = {"Content-Type": "application/json"}
        if fish_tts.api_key:
            headers["Authorization"] = f"Bearer {fish_tts.api_key}"
        if fish_tts.model_name:
            headers["model"] = fish_tts.model_name

        payload: dict = {
            "text": self._input_text,
            "format": "pcm",
            "sample_rate": 44100,
            "latency": "balanced",
            "chunk_length": 300,
            "normalize": True,
        }
        if fish_tts.voice_id:
            payload["reference_id"] = fish_tts.voice_id

        request_id = utils.shortuuid()

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                fish_tts.api_url,
                json=payload,
                headers=headers,
                timeout=30.0,
            ) as response:
                response.raise_for_status()

                # Inicializar el emitter con PCM crudo — sin decodificar mp3
                output_emitter.initialize(
                    request_id=request_id,
                    sample_rate=44100,
                    num_channels=1,
                    mime_type="audio/pcm",
                )

                async for chunk in response.aiter_bytes(chunk_size=4096):
                    output_emitter.push(chunk)

        output_emitter.flush()
