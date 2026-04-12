"""Carga la configuracion de un vertical (config.yaml + persona.md)."""

from pathlib import Path

import yaml

VERTICALS_DIR = Path(__file__).parent.parent.parent / "verticals"


def load_vertical(name: str) -> dict:
    """Carga config.yaml, persona.md y opcionalmente la KB del vertical."""
    path = VERTICALS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Vertical '{name}' no encontrado en {VERTICALS_DIR}")

    with open(path / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with open(path / "persona.md", encoding="utf-8") as f:
        config["persona"] = f.read()

    # Carga la KB como texto plano (fallback cuando el RAG vectorial no esta disponible)
    kb_dir = path / "kb"
    if kb_dir.exists():
        kb_texts = []
        for md_file in sorted(kb_dir.glob("*.md")):
            kb_texts.append(md_file.read_text(encoding="utf-8"))
        if kb_texts:
            config["kb_static"] = "\n\n".join(kb_texts)

    return config
