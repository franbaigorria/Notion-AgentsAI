from core.llm.base import LLMProvider
from core.orchestrator.models import SessionTrace, TurnTrace
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
    ):
        self.llm = llm
        self.tts = tts
        self.telephony = telephony
        self.history: list[dict] = []
        self.session = SessionTrace()

    async def run(self) -> None:
        print("🎙  Agente listo. Escribí tu mensaje (ctrl+c para salir):\n")
        try:
            async for user_input in self.telephony.receive_text():
                turn = await self._process_turn(user_input)
                self.session.turns.append(turn)
                self._print_turn_summary(turn)
        except KeyboardInterrupt:
            pass
        finally:
            self._print_session_summary()

    async def _process_turn(self, user_input: str) -> TurnTrace:
        self.history.append({"role": "user", "content": user_input})

        llm_result = await self.llm.complete(self.history, SYSTEM_PROMPT)
        self.history.append({"role": "assistant", "content": llm_result.content})

        tts_result = await self.tts.synthesize(llm_result.content)
        await self.telephony.play_audio(tts_result.audio)

        return TurnTrace(
            user_input=user_input,
            llm_provider="gpt-4o",
            llm_latency_ms=llm_result.latency_ms,
            llm_cost_usd=llm_result.cost_usd,
            tokens_used=llm_result.input_tokens + llm_result.output_tokens,
            tts_provider="elevenlabs",
            tts_latency_ms=tts_result.latency_ms,
            tts_cost_usd=tts_result.cost_usd,
            total_latency_ms=llm_result.latency_ms + tts_result.latency_ms,
            total_cost_usd=llm_result.cost_usd + tts_result.cost_usd,
        )

    def _print_turn_summary(self, turn: TurnTrace) -> None:
        print(f"\n💬 {turn.llm_provider:<12} {turn.llm_latency_ms:>6.0f}ms  ${turn.llm_cost_usd:.4f}")
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
