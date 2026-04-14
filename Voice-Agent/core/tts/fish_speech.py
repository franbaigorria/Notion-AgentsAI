import os
import httpx
import logging
from livekit.agents import tts, utils

class FishSpeechTTS(tts.TTS):
    def __init__(self, voice_id: str = "", model: str = ""):
        # Fish Audio uses standard 44.1kHz by default for audio generation
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=44100, 
            num_channels=1
        )
        self.voice_id = voice_id
        self.model_name = model
        self.api_url = os.environ.get("FISH_AUDIO_URL", "https://api.fish.audio/v1/tts")
        self.api_key = os.environ.get("FISH_AUDIO_API_KEY", "")

    def synthesize(self, text: str, **kwargs) -> tts.ChunkedStream:
        return _FishChunkedStream(tts=self, input_text=text, conn_options=kwargs.get("conn_options"))
        
    def as_livekit_plugin(self) -> tts.TTS:
        return self

class _FishChunkedStream(tts.ChunkedStream):
    def __init__(self, getattr=None, *, tts: FishSpeechTTS, input_text: str, conn_options=None):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self.text = input_text
        self._tts = tts

    async def _run(self, *args, **kwargs):
        headers = {
            "Content-Type": "application/json"
        }
        if self._tts.api_key:
            headers["Authorization"] = f"Bearer {self._tts.api_key}"
            
        if self._tts.model_name:
            headers["model"] = self._tts.model_name
        
        payload = {
            "text": self.text,
            "format": "mp3", 
        }
        if self._tts.voice_id:
            payload["reference_id"] = self._tts.voice_id
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._tts.api_url, 
                    json=payload, 
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                
                # LiveKit mp3 decoder wrapper avoids complex audio byte parsing
                decoder = utils.codecs.Mp3StreamDecoder()
                
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    frames = decoder.decode_chunk(chunk)
                    for frame in frames:
                        self._event_ch.send_nowait(
                            tts.SynthesizedAudio(
                                text=self.text,
                                data=frame
                            )
                        )
                
                # Flush the stream decoding queue
                frames = decoder.flush()
                for frame in frames:
                    self._event_ch.send_nowait(
                        tts.SynthesizedAudio(
                            text=self.text,
                            data=frame
                        )
                    )
        except Exception as e:
            logging.error(f"FishSpeech TTS synthesis error: {e}")
