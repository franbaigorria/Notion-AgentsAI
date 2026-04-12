"""Flow Engine — detección de intención y guía de conversación estructurada.

Carga flows.yaml del vertical, detecta el flow activo por keyword matching,
y genera una guía en lenguaje natural que se inyecta en el system prompt.

Claude navega los pasos con su propia inteligencia — no hay state machine rígida.
Esto funciona mejor que un script fijo porque el paciente nunca sigue el orden exacto.

Uso:
    from core.flows.engine import FlowEngine
    from pathlib import Path

    engine = FlowEngine.load(Path("verticals/clinica/flows.yaml"))
    flow_name = engine.detect("quiero sacar un turno")  # → "agendar_turno"
    guidance = engine.get_guidance(flow_name)           # → texto para el system prompt
"""

from pathlib import Path

import yaml


# Keywords para retrieval al activar cada flow — tema del flow, no del usuario
_FLOW_RAG_QUERIES: dict[str, str] = {
    "agendar_turno": "especialidades médicas disponibles horarios profesionales turnos",
    "consulta_cobertura": "obras sociales coberturas convenios prepaga plan",
    "info_general": "horarios ubicación dirección teléfono estacionamiento contacto",
    "reagendar_cancelar": "turnos cancelar reagendar cambiar",
}


class FlowEngine:
    def __init__(self, flows: dict):
        self._flows = flows  # {flow_name: {trigger, steps, escalate_if}}
        self._active: str | None = None
        self.flow_context: str | None = None  # contexto RAG persistente del flow activo

    @classmethod
    def load(cls, path: Path) -> "FlowEngine":
        """Carga el flows.yaml del vertical."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(flows=data.get("flows", {}))

    def get_flow_rag_query(self, flow_name: str) -> str:
        """Retorna la query de RAG para recuperar el contexto del flow al activarlo."""
        return _FLOW_RAG_QUERIES.get(flow_name, flow_name.replace("_", " "))

    def detect(self, text: str) -> str | None:
        """Keyword matching contra los triggers de cada flow.

        Retorna el nombre del flow con más keywords presentes en el texto,
        o None si no hay match.
        """
        text_lower = text.lower()
        best_flow = None
        best_count = 0

        for flow_name, flow in self._flows.items():
            count = sum(
                1 for trigger in flow.get("trigger", [])
                if trigger.lower() in text_lower
            )
            if count > best_count:
                best_count = count
                best_flow = flow_name

        return best_flow if best_count > 0 else None

    def activate(self, flow_name: str) -> None:
        """Activa un flow. Lo mantiene hasta que se resetee o cambie."""
        if flow_name in self._flows:
            self._active = flow_name
            self.flow_context = None  # se carga después del RAG

    def reset(self) -> None:
        """Desactiva el flow actual (conversación libre)."""
        self._active = None
        self.flow_context = None

    @property
    def active(self) -> str | None:
        return self._active

    def get_guidance(self, flow_name: str | None = None) -> str | None:
        """Genera la guía de conversación para el flow indicado (o el activo).

        Retorna texto en lenguaje natural listo para inyectar en el system prompt.
        """
        name = flow_name or self._active
        if not name or name not in self._flows:
            return None

        flow = self._flows[name]
        steps = flow.get("steps", [])
        escalate = flow.get("escalate_if", [])

        # Convertir cada step (que puede ser dict o string) a texto natural
        step_lines = []
        for step in steps:
            if isinstance(step, dict):
                for step_name, instruction in step.items():
                    step_lines.append(f"  {len(step_lines) + 1}. {instruction}")
            else:
                step_lines.append(f"  {len(step_lines) + 1}. {step}")

        label = name.replace("_", " ").capitalize()
        guidance = (
            f"--- Guía de conversación: {label} ---\n"
            f"Seguí estos pasos en orden. Completá cada uno antes de avanzar al siguiente.\n"
            f"Si el paciente ya dio la información de un paso, no se la volvás a pedir.\n\n"
            + "\n".join(step_lines)
        )

        if escalate:
            escalate_lines = "\n".join(f"  - {e}" for e in escalate)
            guidance += (
                f"\n\nDerivá a un operador humano si:\n{escalate_lines}"
            )

        guidance += "\n--- Fin de guía ---"
        return guidance
