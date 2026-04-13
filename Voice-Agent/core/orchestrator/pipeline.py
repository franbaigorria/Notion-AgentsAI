from core.llm.base import LLMProvider
from core.orchestrator.models import SessionTrace, TurnTrace
from core.stt.base import STTProvider, STTResult
from core.telephony.base import TelephonyProvider
from core.tts.base import TTSProvider

SYSTEM_PROMPT = """Sos un asistente de voz amigable que habla español rioplatense.
Tus respuestas deben ser cortas y naturales para escuchar — sin bullets, sin markdown, frases de no más de 20 palabras.
Usá un tono cálido y directo."""


class VoicePipeline:
    def __init__(
        self,
        llm: LLMProvider,
        tts: TTSProvider,
        telephony: TelephonyProvider,
        stt: STTProvider | None = None,
    ):
        self.llm = llm
        self.tts = tts
        self.telephony = telephony
        self.stt = stt
        self.history: list[dict] = []
        self.session = SessionTrace()

    async def run(self) -> None:
        mode = "voz" if self.stt else "texto"
        print(f"🎙  Agente listo — modo {mode} (ctrl+c para salir).\n")
        try:
            if self.stt:
                await self._run_voice_mode()
            else:
                await self._run_text_mode()
        except KeyboardInterrupt:
            pass
        finally:
            self._print_session_summary()

    async def _run_voice_mode(self) -> None:
        while True:
            audio, rate = await self.telephony.record_audio()
            stt_result = await self.stt.transcribe(audio, rate)

            if not stt_result.text.strip():
                print("(no se escuchó nada, intentá de nuevo)")
                continue

            print(f'📝 "{stt_result.text}"')
            turn = await self._process_turn(stt_result.text, stt_result)
            self.session.turns.append(turn)
            self._print_turn_summary(turn)

    async def _run_text_mode(self) -> None:
        async for user_input in self.telephony.receive_text():
            turn = await self._process_turn(user_input)
            self.session.turns.append(turn)
            self._print_turn_summary(turn)

    async def _process_turn(
        self, user_input: str, stt_result: STTResult | None = None
    ) -> TurnTrace:
        self.history.append({"role": "user", "content": user_input})

        llm_result = await self.llm.complete(self.history, SYSTEM_PROMPT)
        self.history.append({"role": "assistant", "content": llm_result.content})

        tts_result = await self.tts.synthesize(llm_result.content)
        await self.telephony.play_audio(tts_result.audio)

        stt_latency = stt_result.latency_ms if stt_result else 0.0
        stt_cost = stt_result.cost_usd if stt_result else 0.0

        return TurnTrace(
            user_input=user_input,
            stt_provider="whisper" if stt_result else None,
            stt_latency_ms=stt_result.latency_ms if stt_result else None,
            stt_cost_usd=stt_result.cost_usd if stt_result else None,
            llm_provider="gpt-4o",
            llm_latency_ms=llm_result.latency_ms,
            llm_cost_usd=llm_result.cost_usd,
            tokens_used=llm_result.input_tokens + llm_result.output_tokens,
            tts_provider="elevenlabs",
            tts_latency_ms=tts_result.latency_ms,
            tts_cost_usd=tts_result.cost_usd,
            total_latency_ms=stt_latency + llm_result.latency_ms + tts_result.latency_ms,
            total_cost_usd=stt_cost + llm_result.cost_usd + tts_result.cost_usd,
        )

    def _print_turn_summary(self, turn: TurnTrace) -> None:
        if turn.stt_provider:
            print(f"\n🎧 {turn.stt_provider:<12} {turn.stt_latency_ms:>6.0f}ms  ${turn.stt_cost_usd:.4f}")
        print(f"💬 {turn.llm_provider:<12} {turn.llm_latency_ms:>6.0f}ms  ${turn.llm_cost_usd:.4f}")
        print(f"🔊 {turn.tts_provider:<12} {turn.tts_latency_ms:>6.0f}ms  ${turn.tts_cost_usd:.4f}")
        print("─" * 42)
        print(f"⏱  Total: {turn.total_latency_ms:.0f}ms  |  💰 ${turn.total_cost_usd:.4f}")

    def _print_session_summary(self) -> None:
        if not self.session.turns:
            return
        print(f"\n{'═' * 42}")
        print(f"  Sesión terminada")
        print(f"  Turnos:            {len(self.session.turns)}")
        print(f"  Costo total:       ${self.session.total_cost_usd:.4f}")
        print(f"  Latencia promedio: {self.session.avg_latency_ms:.0f}ms")
        print(f"{'═' * 42}")
