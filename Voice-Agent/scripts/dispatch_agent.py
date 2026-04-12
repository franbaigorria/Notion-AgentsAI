"""Despacha el agente 'clinica' a una room de prueba."""

import asyncio
import os
from dotenv import load_dotenv
from livekit import api
from livekit.api.agent_dispatch_service import AgentDispatchService

load_dotenv()

ROOM_NAME = "test-nanci-2"
AGENT_NAME = "clinica"


async def main():
    lk = api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    # Crear la room si no existe
    await lk.room.create_room(api.CreateRoomRequest(name=ROOM_NAME))
    print(f"Room: {ROOM_NAME}")

    # Despachar el agente
    dispatch_svc = AgentDispatchService(
        lk._session,
        os.environ["LIVEKIT_URL"],
        os.environ["LIVEKIT_API_KEY"],
        os.environ["LIVEKIT_API_SECRET"],
    )
    dispatch = await dispatch_svc.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=AGENT_NAME,
            room=ROOM_NAME,
            metadata='{"vertical": "clinica"}',
        )
    )
    print(f"[OK] Agente despachado: {dispatch}")
    print("Entra a meet.livekit.io con la room 'test-nanci' para escuchar a Nanci.")

    await lk.aclose()


if __name__ == "__main__":
    asyncio.run(main())
