"""Config loader — Voice Agent Platform.

Compartido entre el entrypoint LiveKit (agent.py) y el modo local (local.py).
"""

from pathlib import Path

import yaml

VERTICALS_DIR = Path(__file__).parent.parent.parent / "verticals"


def load_vertical(name: str) -> dict:
    """Carga config.yaml y persona.md del vertical indicado."""
    path = VERTICALS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Vertical '{name}' no encontrado en {VERTICALS_DIR}")

    with open(path / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with open(path / "persona.md", encoding="utf-8") as f:
        config["persona"] = f.read()

    return config
