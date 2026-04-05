"""
Despacha el agente a una sala de LiveKit.

Uso:
    python scripts/dispatch_agent.py
    python scripts/dispatch_agent.py --room mi-sala
"""

import argparse
import asyncio

from dotenv import load_dotenv

load_dotenv()

from livekit.api import LiveKitAPI
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest


async def dispatch(room: str) -> None:
    async with LiveKitAPI() as api:
        result = await api.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(room=room, agent_name="")
        )
        print(f"Agente despachado - room: {room}, dispatch_id: {result.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--room", default="test-room")
    args = parser.parse_args()
    asyncio.run(dispatch(args.room))
