# Session Plan — Voice-Agent (2026-04-12)

## Context

El proyecto **Voice-Agent** es una plataforma de voz real-time multi-vertical (LiveKit + Deepgram + Claude + ElevenLabs). Primer vertical: **Clínica médica argentina** (agente: Nanci). Estado actual: **~25-30% implementado** — la arquitectura de adapters está sólida, los providers base funcionan (Deepgram STT, Claude LLM, ElevenLabs TTS), y la config de Clínica está completa. Pero:

- **No se puede correr end-to-end**: falta telephony (no hay Twilio ni modo local).
- **No hay tests**: `/tests/` está vacío.
- **No hay observabilidad**: los providers reportan `latency_ms` / `cost_usd` pero nadie los agrega.
- **RAG y memoria están stubbeadas**: `rag/base.py` y `memory/base.py` son solo interfaces.

**Objetivo de hoy**: que el agente sea **corribile localmente**, **medible**, y **testeable**. Esto destraba TODO lo que sigue (RAG, memoria, Twilio, flows). Sin runnability local no hay forma de iterar.

### Hallazgos que reformulan el plan

1. **LiveKit ya hace streaming LLM→TTS nativamente.** Los plugins `lk_anthropic.LLM` + `lk_elevenlabs.TTS` manejan chunks por oración dentro de `AgentSession`. El `complete()` de `core/llm/claude.py` es para modo directo (tests/RAG batch), no producción. **La optimización de streaming no es una feature a construir — es verificar que ya funciona.**

2. **El patrón "double-agent" (optimize_for_tts) NO está en el hot path.** Existe en el código pero el orchestrator nunca lo llama. Las restricciones TTS-friendly ya están en `persona.md`. **No hay 1-2s de latency que recuperar acá.**

3. **El orchestrator está acoplado a LiveKit** (`JobContext`, `ctx.room`). Bolt-on de LocalTelephony sobre `AgentSession` es doloroso. **Solución**: entrypoint paralelo direct-mode que usa `complete()`/`synthesize()` directamente.

4. **pytest + pytest-asyncio ya están en `pyproject.toml`.** No hay trabajo de deps.

## Recommended Approach

Cuatro entregables esta sesión, en orden:

### P1 — LocalTelephony + Direct-Mode Entrypoint (~90 min)

Destrabar runnability sin Twilio (RQ-05).

**Archivos nuevos:**
- `core/telephony/local.py` — `LocalTelephony(TelephonyProvider)` con modo `"text"` (stdin/stdout). Modo `"audio"` (sounddevice) se defiere.
- `core/orchestrator/local.py` — función `run_local(vertical, mode="text")`. Paralelo a `entrypoint()` pero sin `AgentSession`. Loop: stdin → `LLMContext` con persona + history (cap 20 msgs) → `ClaudeLLM.complete()` → stdout.
- `core/orchestrator/config.py` — extraer `load_vertical()` de `agent.py` para reusar.

**Archivos a modificar:**
- `core/orchestrator/agent.py` — re-export de `load_vertical` para no romper.

**CLI:** `python -m core.orchestrator.local --vertical clinica --mode text`

### P2 — Streaming en Direct-Mode (~45 min)

LiveKit ya streamea. Esto es solo para el direct-mode (tests + futuro RAG loop).

**Archivos a modificar:**
- `core/llm/base.py` — agregar `async def stream(self, ctx) -> AsyncIterator[str]` (default raise NotImplementedError, NO `@abstractmethod` para no romper).
- `core/llm/claude.py` — implementar `stream()` con `client.messages.stream()`.
- `core/orchestrator/local.py` — en modo audio (futuro), acumular tokens en buffer por oración (`re.split(r'([.!?]\s)', ...)`) y flushear cada oración completa a TTS concurrente.
- `docs/architecture.md` — una línea documentando que LK maneja streaming en el pipeline real-time.

### P3 — Observability Decorator (~60 min)

Satisface RQ-03 y RQ-04 — medir latencia y costo por call.

**Archivo nuevo:**
- `core/observability/tracing.py` — `@track(provider, operation)` decorator para métodos async que retornan objetos con `latency_ms`/`cost_usd`. Emite JSON estructurado (`{call_id, provider, operation, latency_ms, cost_usd, timestamp}`) a stdout por default; configurable vía env `OBSERVABILITY_SINK` (`stdout`, `file:/path`, `none`). ContextVar `current_call_id` para correlacionar eventos de un turno.

**Archivos a modificar:**
- `core/llm/claude.py` — decorar `complete()`.
- `core/stt/deepgram.py` — decorar `transcribe()`.
- `core/tts/elevenlabs.py` — `synthesize()` es async generator; usar wrapper separado `record_tts_stream()` que mide duración total al cerrar.

**Nota documentada**: solo instrumenta direct-mode. Instrumentar el pipeline LiveKit requiere el event bus de LK — Phase 3+.

### P4 — Smoke Test (~30 min)

**Archivos nuevos:**
- `tests/fakes.py` — `FakeLLMProvider`, `FakeSTTProvider`, `FakeTTSProvider` con respuestas canned.
- `tests/test_smoke.py` — 3 tests mínimos:
  1. `run_local(vertical="clinica", mode="text")` con stdin "Quiero un turno" → verifica que LLM fue invocado con persona system prompt y respuesta salió a stdout.
  2. `ClaudeLLM.complete()` con `anthropic` SDK mockeado via `unittest.mock`.
  3. Decorador observability emite evento con campos correctos.

**Archivos a modificar:**
- `pyproject.toml` — verificar `[tool.pytest.ini_options]` tiene `asyncio_mode = "auto"`.

### Deferred (explícito — no hacer hoy)

- **RAG (Phase 2)** — fase completa. Próxima sesión con fundaciones calientes.
- **Audio mode en LocalTelephony** — requiere `sounddevice`, no bloquea nada hoy.
- **Graceful degradation (RQ-06)** — prematuro, requiere fallback providers configurados.
- **Twilio / telephony real** — Phase 3+.
- **Cleanup de `optimize_for_tts`** — no es hot path. Solo agregar nota en docstring (~10 min, lo incluyo en P3).

## Critical Files

**Nuevos:**
- `core/telephony/local.py`
- `core/orchestrator/local.py`
- `core/orchestrator/config.py`
- `core/observability/tracing.py`
- `tests/fakes.py`
- `tests/test_smoke.py`

**Modificados:**
- `core/orchestrator/agent.py` — extraer `load_vertical`
- `core/llm/base.py` — agregar `stream()` abstracto con default
- `core/llm/claude.py` — implementar `stream()` + decorator + docstring nota
- `core/stt/deepgram.py` — decorator
- `core/tts/elevenlabs.py` — wrapper de streaming para observability
- `docs/architecture.md` — nota sobre streaming nativo de LK
- `pyproject.toml` — verificar config pytest

## Reuse (no reinventar)

- `load_vertical()` en `core/orchestrator/agent.py` — extraer y compartir.
- `ClaudeLLM.complete()` — ya retorna `LLMResult` con `latency_ms` + `cost_usd`. Perfecto para direct mode.
- `Message` + `LLMContext` dataclasses en `core/llm/base.py` — conversation history container.
- `ElevenLabsTTS.synthesize()` — async byte stream, funciona as-is para modo audio futuro.
- `verticals/clinica/persona.md` — ya tiene restricciones TTS-friendly (frases cortas, sin bullets, español argentino).

## Riesgos y Mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Extraer `load_vertical` rompe el entrypoint actual | Re-export desde `agent.py`; correr `python -m core.orchestrator.agent dev` para verificar |
| Context del loop local crece sin límite | Cap history a 20 mensajes; memoria persistente viene en Phase 4 |
| Decorator sobre async generator (`synthesize`) | Wrapper explícito `record_tts_stream()` — no `@functools.wraps` (los generators necesitan otro tratamiento) |
| LiveKit streaming no funciona como se asume | Correr `agent.py dev` contra un room real y medir time-to-first-audio en logs de LK. Si > 2s, investigar flags |
| `sounddevice` en Windows (modo audio futuro) | Modo audio está DIFERIDO. Text mode no lo requiere |

## Verification

Cada pieza se prueba así:

| Pieza | Cómo probarla |
|-------|---------------|
| LocalTelephony + run_local | `echo "Hola" \| python -m core.orchestrator.local --vertical clinica --mode text` → responde estilo Nanci en < 3s |
| Streaming direct-mode | Timestamps en el sentence-flush loop — primera oración emitida antes de que termine el LLM |
| LiveKit streaming (verif) | Correr `python -m core.orchestrator.agent dev`, medir time-to-first-audio en logs |
| Observability | Post-run, stdout contiene ≥3 líneas JSON (llm/stt/tts) con `latency_ms` poblado y `call_id` común |
| Tests | `pytest tests/ -v` → 3/3 passing en < 5s |
| RQ-05 | Pipeline completo sin `LIVEKIT_URL` ni Twilio |

## Session Time Budget

Total estimado: **~3.5-4 horas** para los 4 entregables con margen.

- P1: 90 min
- P2: 45 min
- P3: 60 min + 10 min docstring cleanup
- P4: 30 min
- Buffer: ~30 min

Si se pisa tiempo: recortar P3 al decorator mínimo (solo `complete()` y `transcribe()`, skip TTS wrapper).

## Qué queda para la próxima sesión

- **Phase 2 — Autonomous RAG**: Qdrant + FastEmbed + Firecrawl ingestion + relevance scoring + web fallback. Es una sesión entera.
- **Conectar flows.yaml al LLM**: intent detection + state machine. Phase 3.
- **Memory persistente (Mem0)**: Phase 4.
- **Twilio webhook + LiveKit bridge**: Phase 3+.
- **Dashboard** (consume los eventos del observability que armamos hoy): Phase 7.
