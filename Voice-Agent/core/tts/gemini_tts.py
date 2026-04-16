"""Gemini TTS — wrapper para LiveKit Agents 1.x.

Usa el SDK google-genai (transitivo de livekit-plugins-google) para llamar a
gemini-3.1-flash-tts-preview y emite audio PCM a través del AudioEmitter de LiveKit.

El modelo soporta style directives mediante texto prepended al input
(patrón idéntico al livekit.plugins.google.beta.GeminiTTS).

Voces disponibles: Charon (default), Puck, Kore, Fenrir, Aoede, Zephyr, y más.
Ver: https://ai.google.dev/gemini-api/docs/speech-generation

Uso en AgentSession (LiveKit Agents 1.x):
    tts = GeminiTTS(voice="Charon", instructions="Respondé con calidez.")
    session = AgentSession(tts=tts.as_livekit_plugin(), ...)

Variable requerida: GEMINI_API_KEY
"""

import logging
import os

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError
from livekit.agents import APIConnectionError, APIStatusError, DEFAULT_API_CONNECT_OPTIONS, tts, utils

from .base import TTSProvider, TTSResult, strip_tone_tags

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 24000
_NUM_CHANNELS = 1
_COST_PER_CHAR_USD = 0.000010  # estimado — actualizar cuando Google publique pricing oficial


class GeminiTTS(TTSProvider, tts.TTS):
    """TTS via Google Gemini generative model — dual-inheritance adapter.

    Hereda de TTSProvider (interfaz interna) y livekit.agents.tts.TTS (contrato
    LiveKit), siguiendo el patrón de FishSpeechTTS.

    Args:
        voice: Nombre de la voz prebuilt. Default: "Charon".
        model: ID del modelo. Default: "gemini-3.1-flash-tts-preview".
        instructions: Directiva de estilo/tono. Se prepende al input text antes
                      de la llamada a la API. None = sin directiva.
    """

    def __init__(
        self,
        voice: str = "Charon",
        model: str = "gemini-3.1-flash-tts-preview",
        instructions: str | None = None,
    ):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=_SAMPLE_RATE,
            num_channels=_NUM_CHANNELS,
        )
        self.voice = voice
        self.model_name = model
        self.instructions = instructions

        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no está configurada")

        self._client = genai.Client(api_key=self.api_key)

    def synthesize(  # type: ignore[override]
        self, text: str, *, conn_options=None, **kwargs
    ) -> "tts.ChunkedStream":
        """Crea un ChunkedStream para la síntesis.

        strip_tone_tags se aplica aquí antes de construir el stream.
        Satisface TTSProvider.synthesize (ABC) y livekit.tts.TTS.synthesize.
        """
        return _GeminiChunkedStream(
            tts=self,
            input_text=strip_tone_tags(text),
            conn_options=conn_options or DEFAULT_API_CONNECT_OPTIONS,
        )

    def as_livekit_plugin(self) -> "tts.TTS":
        """Devuelve self — GeminiTTS ya hereda de livekit.tts.TTS."""
        return self

    def estimate_cost(self, text: str) -> TTSResult:
        """Estimación de costo basada en caracteres (pricing provisional)."""
        return TTSResult(
            latency_ms=0,
            cost_usd=len(text) * _COST_PER_CHAR_USD,
            provider="gemini",
        )


class _GeminiChunkedStream(tts.ChunkedStream):
    """Stream de audio que llama a Gemini generate_content con AUDIO modality.

    Implementa el contrato _run(output_emitter) de LiveKit Agents 1.x.
    Patrón idéntico a livekit.plugins.google.beta.gemini_tts.ChunkedStream.
    """

    def __init__(
        self,
        *,
        tts: GeminiTTS,
        input_text: str,
        conn_options,
    ):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        gemini_tts: GeminiTTS = self._tts  # type: ignore[assignment]

        try:
            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=gemini_tts.voice,
                        )
                    )
                ),
            )

            input_text = self._input_text
            if gemini_tts.instructions is not None:
                input_text = f'{gemini_tts.instructions}:\n"{input_text}"'

            response = await gemini_tts._client.aio.models.generate_content(
                model=gemini_tts.model_name,
                contents=input_text,
                config=config,
            )

            output_emitter.initialize(
                request_id=utils.shortuuid(),
                sample_rate=gemini_tts.sample_rate,
                num_channels=gemini_tts.num_channels,
                mime_type="audio/pcm",
            )

            if (
                not response.candidates
                or not (content := response.candidates[0].content)
                or not content.parts
            ):
                raise APIStatusError("No audio content generated")

            for part in content.parts:
                if (
                    (inline_data := part.inline_data)
                    and inline_data.data
                    and inline_data.mime_type
                    and inline_data.mime_type.startswith("audio/")
                ):
                    output_emitter.push(inline_data.data)

            output_emitter.flush()

        except ClientError as e:
            raise APIStatusError(
                "gemini tts: client error",
                status_code=e.code,
                body=f"{e.message} {e.status}",
                retryable=True if e.code in {429, 499} else False,
            ) from e
        except ServerError as e:
            raise APIStatusError(
                "gemini tts: server error",
                status_code=e.code,
                body=f"{e.message} {e.status}",
                retryable=True,
            ) from e
        except APIError as e:
            raise APIStatusError(
                "gemini tts: api error",
                status_code=e.code,
                body=f"{e.message} {e.status}",
                retryable=True,
            ) from e
        except (APIStatusError, APIConnectionError):
            raise
        except Exception as e:
            raise APIConnectionError(
                f"gemini tts: error generating speech {str(e)}",
                retryable=True,
            ) from e
