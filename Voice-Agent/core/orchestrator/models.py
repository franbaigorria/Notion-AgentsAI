from dataclasses import dataclass, field


@dataclass
class TurnTrace:
    user_input: str
    llm_provider: str
    llm_latency_ms: float
    llm_cost_usd: float
    tokens_used: int
    tts_provider: str
    tts_latency_ms: float
    tts_cost_usd: float
    total_latency_ms: float
    total_cost_usd: float
    stt_provider: str | None = None
    stt_latency_ms: float | None = None
    stt_cost_usd: float | None = None


@dataclass
class SessionTrace:
    turns: list[TurnTrace] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return sum(t.total_cost_usd for t in self.turns)

    @property
    def avg_latency_ms(self) -> float:
        if not self.turns:
            return 0.0
        return sum(t.total_latency_ms for t in self.turns) / len(self.turns)
