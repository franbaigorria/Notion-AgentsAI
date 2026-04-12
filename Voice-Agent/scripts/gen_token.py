"""Genera un token de acceso para unirse a una room de LiveKit desde meet.livekit.io."""

import os
from dotenv import load_dotenv
from livekit.api import AccessToken, VideoGrants

load_dotenv()

room_name = "test-nanci-2"
identity = "tester"

token = (
    AccessToken(
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    .with_identity(identity)
    .with_grants(VideoGrants(room_join=True, room=room_name))
    .to_jwt()
)

print(f"\nURL:   {os.environ['LIVEKIT_URL']}")
print(f"Token: {token}\n")
