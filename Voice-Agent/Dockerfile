# Usamos la imagen oficial de python con uv preinstalado
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Configuramos variables de entorno para python y uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copiamos primero la definicion de dependencias para aprovechar la cache de Docker
COPY pyproject.toml uv.lock ./

# Instalamos las dependencias
RUN uv sync --frozen --no-dev --no-install-project

# Copiamos el resto del codigo
COPY . .

# Modo de operación: pipeline | realtime (override desde Railway env vars)
ENV AGENT_MODE=pipeline

# Comando de inicio — el launcher despacha al agente correcto según AGENT_MODE
CMD ["uv", "run", "python", "-m", "apps.launcher", "start"]
