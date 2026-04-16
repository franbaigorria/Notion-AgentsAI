"""Test auditivo del sistema de tonos Fish Audio S2 Pro.

Genera un archivo de audio por cada tono definido, usando la misma frase base
pero con el tag correspondiente. Escuchá los archivos y comparalos.

Uso:
    uv run python scripts/test_fish_tones.py

Los audios se guardan en /tmp/fish_tones/*.wav
"""

import asyncio
import os
import sys
from pathlib import Path

# Asegurar imports desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core.tts.fish_speech import FishSpeechTTS


# ─── Casos de prueba ──────────────────────────────────────────────────────────
# Cada tupla: (nombre_archivo, texto_con_tone_tag)

TEST_CASES = [
    ("01_sin_tono",     "Hola, ¿en qué te puedo ayudar?"),
    ("02_excited",      "<tone:excited>Hola, ¿en qué te puedo ayudar?"),
    ("03_empathetic",   "<tone:empathetic>Entiendo, debe ser frustrante esa situación."),
    ("04_soft",         "<tone:soft>No te preocupes, lo vemos juntos."),
    ("05_pause",        "<tone:pause>La dirección es Av. Corrientes 1234, piso 3."),
    ("06_cheerful",     "<tone:cheerful>Listo. Cualquier cosa nos llamás. Buen día."),
    # Prueba de robustez — tag de cierre no debe aparecer en audio
    ("07_cierre_strip", "<tone:excited>¡Listo! Te quedó el turno.</tone:excited>"),
]


async def synthesize_to_file(tts: FishSpeechTTS, text: str, out_path: Path) -> None:
    preprocessed = tts.preprocess_text(text)
    print(f"  original:     {text!r}")
    print(f"  → Fish Audio: {preprocessed!r}")

    import httpx

    headers = {"Content-Type": "application/json"}
    if tts.api_key:
        headers["Authorization"] = f"Bearer {tts.api_key}"
    if tts.model_name:
        headers["model"] = tts.model_name

    payload = {
        "text": preprocessed,
        "format": "pcm",
        "sample_rate": 44100,
        "latency": "balanced",
        "chunk_length": 300,
        "normalize": True,
    }
    if tts.voice_id:
        payload["reference_id"] = tts.voice_id

    raw_pcm = bytearray()
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", tts.api_url, json=payload, headers=headers, timeout=30.0
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(4096):
                raw_pcm.extend(chunk)

    # PCM → WAV (header mínimo para poder abrir con cualquier player)
    _write_wav(out_path, bytes(raw_pcm), sample_rate=44100, channels=1)
    print(f"  ✓ guardado en {out_path}\n")


def _write_wav(path: Path, pcm: bytes, sample_rate: int, channels: int) -> None:
    import struct
    bits = 16
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_len = len(pcm)
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_len))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits))
        f.write(b"data")
        f.write(struct.pack("<I", data_len))
        f.write(pcm)


async def main() -> None:
    api_key = os.environ.get("FISH_AUDIO_API_KEY", "")
    if not api_key:
        print("ERROR: FISH_AUDIO_API_KEY no está seteada en .env")
        sys.exit(1)

    out_dir = Path("/tmp/fish_tones")
    out_dir.mkdir(exist_ok=True)

    tts = FishSpeechTTS(model="s2-pro")

    print(f"Generando {len(TEST_CASES)} audios en {out_dir}/\n")

    for name, text in TEST_CASES:
        print(f"[{name}]")
        out_path = out_dir / f"{name}.wav"
        try:
            await synthesize_to_file(tts, text, out_path)
        except Exception as e:
            print(f"  ✗ error: {e}\n")

    print("Listo. Abrí los archivos con:")
    print(f"  open {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
