"""Test directo de ElevenLabs TTS — sin LiveKit."""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from elevenlabs.client import AsyncElevenLabs

VOICE_ID = "07BApwwAuIPJ9y3d8YQo"
TEXT = "Hola, soy Nanci. En que te puedo ayudar?"


async def main():
    client = AsyncElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

    print(f"Probando voz: {VOICE_ID}")
    print(f"Texto: {TEXT}\n")

    # Probar con eleven_turbo_v2_5
    for model in ["eleven_turbo_v2_5", "eleven_multilingual_v2", "eleven_flash_v2_5"]:
        print(f"Modelo: {model}...")
        try:
            chunks = []
            async for chunk in client.text_to_speech.convert(
                voice_id=VOICE_ID,
                text=TEXT,
                model_id=model,
                output_format="mp3_44100_128",
            ):
                if chunk:
                    chunks.append(chunk)

            total = sum(len(c) for c in chunks)
            print(f"  OK — {total} bytes de audio recibidos\n")
            break
        except Exception as e:
            print(f"  ERROR: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
