import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    livekit_url: str = os.environ["LIVEKIT_URL"]
    livekit_api_key: str = os.environ["LIVEKIT_API_KEY"]
    livekit_api_secret: str = os.environ["LIVEKIT_API_SECRET"]

    anthropic_api_key: str = os.environ["ANTHROPIC_API_KEY"]

    elevenlabs_api_key: str = os.environ["ELEVENLABS_API_KEY"]
    elevenlabs_voice_id: str = os.environ["ELEVENLABS_VOICE_ID"]

    deepgram_api_key: str = os.environ["DEEPGRAM_API_KEY"]
