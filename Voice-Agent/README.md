# Agente de Voz Argentino

Voice agent con acento argentino que responde sobre datos de negocio usando RAG. Pensado para soporte, seguimiento y ventas simples en pymes latinoamericanas. 

Stack optimizado para **Ultra-Baja Latencia (Sub-300ms)**: 
* Orquestación: **LiveKit Agents**
* LLM: **Groq (Llama-3.1-8b-instant)**
* TTS: **Deepgram Aura (ajustado para acento local) / ElevenLabs**
* STT: **Deepgram Nova 3**
* Despliegue: **Railway (US-East)**

El diferenciador crítico es la naturalidad local, la inmediatez cognitiva (E2E delay ~250ms) y el comportamiento conversacional.

---

## 🚀 Arquitectura "Edge-Cloud Dual-Loop"
Para romper la barrera de los 800ms de latencia, el orquestador backend fue migrado de local a un contenedor nativo en Railway (US-East). 
Esto elimina la penalidad de red del "round-trip" entre Sudamérica y las APIs de LLM/TTS ubicadas en USA.

### Métricas de Rendimiento Registradas
Al correr en el mismo eje de datacenter que los proveedores, se obtuvieron latencias de clase mundial:
* **LLM TTFT (Time to First Token):** ~130ms. (Groq API, procesado sobre LPUs).
* **TTS TTFB (Time to First Byte):** ~75ms - ~120ms. (Deepgram Aura Streaming).
* **Latencia Percibida E2E:** **~250ms flat**. (*Desde el momento que el usuario finaliza la frase hasta que escucha la voz de vuelta, sin contar la retención por VAD de 0.5s*).

---

## 🛠️ Despliegue en Railway

El proyecto está dockerizado usando `uv` para builds rápidos en producción.

### Requisitos (Variables de Entorno)
En la plataforma de hosting se deben proveer las siguientes claves:
- `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`
- `GROQ_API_KEY` (Obligatoria para la velocidad ~130ms de LLM)
- `DEEPGRAM_API_KEY` (Para STT/TTS)
- *(Opcional)* `ELEVENLABS_API_KEY` si decides volver a ElevenLabs prestando atención a los cuellos de cuota (Rate Limit) que causan errores `no audio frames pushed`.

*Importante: Railway requiere configurar el `Root Directory` apuntando a `/Voice-Agent`.*

---

## 📚 Workspace

Todo el trabajo del equipo se registra en Notion (teamspace: Agent AI). Ver `.agents/skills/voice-agent-workspace/SKILL.md` para el protocolo completo de cómo y dónde guardar cada tipo de información.
