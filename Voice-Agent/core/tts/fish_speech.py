"""Fish Audio TTS — wrapper para LiveKit Agents 1.5.x.

Consume el endpoint REST /v1/tts de Fish Audio y emite audio
a través del AudioEmitter de LiveKit (contrato ChunkedStream._run).

Uso:
    tts = FishSpeechTTS(voice_id="...", model="s1")
    session = AgentSession(tts=tts, ...)
"""

import os
import logging

import httpx
from livekit.agents import tts, utils

logger = logging.getLogger(__name__)


class FishSpeechTTS(tts.TTS):
    def __init__(self, voice_id: str = "", model: str = "s1"):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=44100,
            num_channels=1,
        )
        self.voice_id = voice_id
        self.model_name = model
        self.api_url = os.environ.get("FISH_AUDIO_URL", "https://api.fish.audio/v1/tts")
        self.api_key = os.environ.get("FISH_AUDIO_API_KEY", "")

    def synthesize(
        self, text: str, *, conn_options=None, **kwargs
    ) -> "tts.ChunkedStream":
        return _FishChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options or tts.DEFAULT_API_CONNECT_OPTIONS,
        )

    def as_livekit_plugin(self) -> "tts.TTS":
        """Adapter bridge — devuelve self porque ya hereda de tts.TTS."""
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
