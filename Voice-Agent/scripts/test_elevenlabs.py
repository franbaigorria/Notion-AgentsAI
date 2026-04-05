"""
Script de prueba de ElevenLabs TTS.

Uso:
    python scripts/test_elevenlabs.py
    python scripts/test_elevenlabs.py --text "Hola, soy tu asistente de la clínica"
    python scripts/test_elevenlabs.py --list-voices

Requiere .env con:
    ELEVENLABS_API_KEY
    ELEVENLABS_VOICE_ID
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv()

SAMPLE_TEXT = (
    "Hola, buenas tardes. Soy Valentina, la asistente virtual de la clínica. "
    "¿En qué te puedo ayudar hoy?"
)


def get_client() -> ElevenLabs:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: ELEVENLABS_API_KEY no está configurada en .env")
        sys.exit(1)
    return ElevenLabs(api_key=api_key)


def list_voices(client: ElevenLabs) -> None:
    voices = client.voices.get_all()
    print(f"\n{'ID':<25} {'Nombre':<30} {'Idiomas'}")
    print("-" * 75)
    for v in voices.voices:
        labels = v.labels or {}
        lang = labels.get("language", "—")
        print(f"{v.voice_id:<25} {v.name:<30} {lang}")


def generate_audio(client: ElevenLabs, text: str, output_path: Path) -> None:
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    if not voice_id:
        print("Error: ELEVENLABS_VOICE_ID no está configurada en .env")
        sys.exit(1)

    print(f"\nGenerando audio para:\n  \"{text}\"\n")
    print(f"Voice ID: {voice_id}")

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)

    size_kb = output_path.stat().st_size / 1024
    print(f"Audio guardado en: {output_path} ({size_kb:.1f} KB)")
    print("\nPara escucharlo:")
    print(f"  start {output_path}  (Windows)")
    print(f"  open {output_path}   (Mac)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test de voz ElevenLabs")
    parser.add_argument("--text", default=SAMPLE_TEXT, help="Texto a convertir a voz")
    parser.add_argument("--output", default="output/test_voz.mp3", help="Archivo de salida")
    parser.add_argument("--list-voices", action="store_true", help="Listar voces disponibles")
    args = parser.parse_args()

    client = get_client()

    if args.list_voices:
        list_voices(client)
        return

    generate_audio(client, args.text, Path(args.output))


if __name__ == "__main__":
    main()
