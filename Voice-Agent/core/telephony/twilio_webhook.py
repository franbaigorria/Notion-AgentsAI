"""Webhook Flask para Twilio — responde con TwiML que conecta la llamada a LiveKit SIP.

Levantarlo en el puerto 8080 (matchea el ngrok que ya está corriendo):
    python -m core.telephony.twilio_webhook

Variables de entorno requeridas (.env):
    LIVEKIT_URL         URL del servidor LiveKit (wss://...)
    TWILIO_PHONE_NUMBER Número de Twilio en formato E.164
"""

import os

from dotenv import load_dotenv
from flask import Flask, Response, request

load_dotenv()

app = Flask(__name__)

_PORT = 8080


def _derive_sip_host(lk_url: str) -> str:
    """Convierte wss://project.livekit.cloud → project.sip.livekit.cloud."""
    host = lk_url.replace("wss://", "").replace("ws://", "").rstrip("/")
    if ".livekit.cloud" in host:
        subdomain = host.split(".livekit.cloud")[0]
        return f"{subdomain}.sip.livekit.cloud"
    return host


def _build_twiml(sip_uri: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial>
    <Sip>{sip_uri}</Sip>
  </Dial>
</Response>"""


@app.route("/voice", methods=["GET", "POST"])
def voice():
    """Twilio llama acá cuando entra una llamada al número."""
    call_sid = request.form.get("CallSid", "unknown")
    from_number = request.form.get("From", "unknown")
    print(f"[Twilio] Llamada entrante — CallSid: {call_sid} | From: {from_number}")

    lk_url = os.environ["LIVEKIT_URL"]
    twilio_number = os.environ["TWILIO_PHONE_NUMBER"]
    sip_host = _derive_sip_host(lk_url)
    sip_uri = f"sip:{twilio_number}@{sip_host};transport=tls"

    print(f"[Twilio] Conectando a LiveKit SIP: {sip_uri}")
    return Response(_build_twiml(sip_uri), content_type="application/xml")


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "port": _PORT}


if __name__ == "__main__":
    print(f"[Webhook] Levantando servidor en http://0.0.0.0:{_PORT}")
    print(f"[Webhook] Endpoint de Twilio: POST /voice")
    app.run(host="0.0.0.0", port=_PORT, debug=False)
