"""Lista todas las voces disponibles en la cuenta de ElevenLabs."""
import os
from dotenv import load_dotenv
load_dotenv()

from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
voices = client.voices.get_all()
for v in voices.voices:
    print(f"{v.voice_id}  {v.name}")
