"""Setup one-time -- configura LiveKit SIP trunk + dispatch rule para recibir llamadas de Twilio.

Correr UNA VEZ antes de levantar el agente:
    python scripts/setup_sip.py

Si ya existe un trunk para el numero, lo reutiliza en lugar de crear uno nuevo.

Variables de entorno requeridas (.env):
    LIVEKIT_URL         URL del servidor LiveKit (wss://...)
    LIVEKIT_API_KEY     API key de LiveKit
    LIVEKIT_API_SECRET  API secret de LiveKit
    TWILIO_PHONE_NUMBER Numero de Twilio en formato E.164 (ej: +12025551234)
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from livekit import api


def _derive_sip_host(lk_url: str) -> str:
    """Convierte wss://project.livekit.cloud -> project.sip.livekit.cloud."""
    host = lk_url.replace("wss://", "").replace("ws://", "").rstrip("/")
    if ".livekit.cloud" in host:
        subdomain = host.split(".livekit.cloud")[0]
        return f"{subdomain}.sip.livekit.cloud"
    return host  # self-hosted: usar el host directamente


async def _find_existing_trunk(lk: api.LiveKitAPI, phone_number: str) -> str | None:
    """Busca un trunk inbound existente que ya tenga el numero registrado.

    Retorna el trunk_id si lo encuentra, None si no.
    """
    try:
        response = await lk.sip.list_inbound_trunk(api.ListSIPInboundTrunkRequest())
        for trunk in response.items:
            if phone_number in trunk.numbers:
                return trunk.sip_trunk_id
    except Exception as e:
        print(f"[WARN] No se pudo listar trunks existentes: {e}")
    return None


async def setup() -> None:
    lk_url = os.environ["LIVEKIT_URL"]
    twilio_number = os.environ.get("TWILIO_PHONE_NUMBER", "")

    if not twilio_number:
        print("ERROR: falta TWILIO_PHONE_NUMBER en .env (formato: +12025551234)")
        return

    lk = api.LiveKitAPI(
        url=lk_url,
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    print(f"Conectado a LiveKit: {lk_url}")
    print(f"Numero Twilio: {twilio_number}\n")

    # 1. Reutilizar trunk existente o crear uno nuevo
    trunk_id = await _find_existing_trunk(lk, twilio_number)

    if trunk_id:
        print(f"[OK] Trunk existente encontrado: {trunk_id} (reutilizando)")
    else:
        print("Creando SIP inbound trunk...")
        trunk = await lk.sip.create_inbound_trunk(
            api.CreateSIPInboundTrunkRequest(
                trunk=api.SIPInboundTrunkInfo(
                    name="Clinica San Martin",
                    numbers=[twilio_number],
                )
            )
        )
        trunk_id = trunk.sip_trunk_id
        print(f"[OK] Trunk creado: {trunk_id}")

    # 2. Crear dispatch rule -- room individual por llamada + auto-dispatch del agente
    print("Creando dispatch rule...")
    rule = await lk.sip.create_dispatch_rule(
        api.CreateSIPDispatchRuleRequest(
            rule=api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix="call-",
                )
            ),
            trunk_ids=[trunk_id],
            room_config=api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name="clinica",
                        metadata='{"vertical": "clinica"}',
                    )
                ]
            ),
        )
    )
    print(f"[OK] Dispatch rule creada: {rule.sip_dispatch_rule_id}")

    # 3. Derivar SIP URI
    sip_host = _derive_sip_host(lk_url)
    sip_uri = f"sip:{twilio_number}@{sip_host};transport=tls"

    print(f"""
============================================================
Configuracion de LiveKit lista.

Ahora configura Twilio:

1. Anda al dashboard de Twilio
2. Phone Numbers -> Manage -> Active Numbers -> tu numero
3. En "Voice Configuration" -> "A call comes in" -> Webhook
4. Pega la URL del ngrok + /voice:
   https://plethora-bullfrog-frown.ngrok-free.dev/voice
5. Metodo: HTTP POST
6. Guarda.

SIP URI generado (para referencia):
   {sip_uri}

Despues levanta el agente en una terminal:
   VERTICAL=clinica .venv\\Scripts\\python -m core.orchestrator.agent start

Y el webhook en otra terminal:
   .venv\\Scripts\\python -m core.telephony.twilio_webhook
============================================================
""")

    await lk.aclose()


if __name__ == "__main__":
    asyncio.run(setup())
