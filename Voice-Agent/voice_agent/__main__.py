import asyncio
import os
import sys

from dotenv import load_dotenv


def check_env() -> None:
    load_dotenv()
    required = ["OPENAI_API_KEY", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Error: faltan variables de entorno: {', '.join(missing)}")
        print("Copiá env.example a .env y completá los valores.")
        sys.exit(1)


async def main() -> None:
    check_env()

    from core.llm.openai_llm import OpenAILLM
    from core.orchestrator.pipeline import VoicePipeline
    from core.telephony.local_input import LocalInput
    from core.tts.elevenlabs_tts import ElevenLabsTTS

    llm = OpenAILLM(api_key=os.environ["OPENAI_API_KEY"])
    tts = ElevenLabsTTS(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        voice_id=os.environ["ELEVENLABS_VOICE_ID"],
    )
    telephony = LocalInput()

    pipeline = VoicePipeline(llm=llm, tts=tts, telephony=telephony)
    await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())
