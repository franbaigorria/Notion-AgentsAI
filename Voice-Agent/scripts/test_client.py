"""scripts/test_client.py — Dispatch the voice-agent and wait for it to join a room.

Designed for a human operator to validate an end-to-end deploy on Railway:
  1. Dispatches the configured agent into a room with ``tenant_id`` in metadata.
  2. Generates a participant JWT so the operator can join the same room with a
     browser client (LiveKit Agents Playground: https://agents-playground.livekit.io/).
  3. Polls ``list_participants`` until the agent participant appears (or timeout).

This script talks ONLY to the LiveKit server-side API (``livekit.api``). It does
NOT stream audio itself — use the printed Playground URL to actually interact.

Usage::

    export LIVEKIT_URL="wss://<project>.livekit.cloud"
    export LIVEKIT_API_KEY="<api key>"
    export LIVEKIT_API_SECRET="<api secret>"

    uv run python scripts/test_client.py --tenant-id <UUID>

Exit codes:
  0 — dispatch succeeded AND agent joined within the timeout
  1 — env var missing or argparse error
  2 — LiveKit API error (dispatch rejected, auth failure, etc.)
  3 — timeout waiting for agent to join
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any

from livekit.api import (
    AccessToken,
    CreateAgentDispatchRequest,
    LiveKitAPI,
    ListParticipantsRequest,
    VideoGrants,
)

# Agent ParticipantKind from livekit-protocol (enum int). See livekit_models.proto.
_PARTICIPANT_KIND_AGENT = 2


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    """Return env var value or exit 1 with a descriptive error."""
    value = os.getenv(name)
    if not value:
        print(f"ERROR: {name} environment variable is required but not set.", file=sys.stderr)
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args. Returns argparse.Namespace with typed fields."""
    parser = argparse.ArgumentParser(
        prog="test_client",
        description="Dispatch the voice-agent and wait for it to join a room.",
    )
    parser.add_argument(
        "--tenant-id",
        type=uuid.UUID,
        required=True,
        help="Tenant UUID — embedded in job metadata so the agent can load TenantContext",
    )
    parser.add_argument(
        "--room",
        type=str,
        default=None,
        help="Room name (default: auto-generated UUID-based)",
    )
    parser.add_argument(
        "--agent-name",
        type=str,
        default="pipeline-agent",
        help="Registered agent name to dispatch (default: pipeline-agent)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Seconds to wait for the agent to join the room (default: 60)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Dispatch + token helpers (pure — unit-testable without LiveKit)
# ---------------------------------------------------------------------------


def _build_dispatch_request(
    *, tenant_id: uuid.UUID, room: str, agent_name: str
) -> CreateAgentDispatchRequest:
    """Build the proto message dispatched to LiveKit.

    The agent reads ``ctx.job.metadata`` as a JSON string in
    ``_extract_tenant_id_from_job`` — we encode ``{"tenant_id": "..."}``.
    """
    metadata_json = json.dumps({"tenant_id": str(tenant_id)})
    return CreateAgentDispatchRequest(
        agent_name=agent_name,
        room=room,
        metadata=metadata_json,
    )


def _generate_participant_token(
    *, api_key: str, api_secret: str, room: str, identity: str
) -> str:
    """Return a JWT with can_publish / can_subscribe grants for the given room."""
    at = AccessToken(api_key, api_secret)
    at.with_identity(identity).with_grants(
        VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
        )
    )
    return at.to_jwt()


# ---------------------------------------------------------------------------
# Core dispatch + poll loop
# ---------------------------------------------------------------------------


async def dispatch_and_wait(
    *,
    livekit_url: str,
    api_key: str,
    api_secret: str,
    tenant_id: uuid.UUID,
    room: str,
    agent_name: str,
    timeout_seconds: float,
    poll_interval: float = 1.0,
) -> dict[str, Any]:
    """Dispatch the agent and poll until it joins.

    Returns a dict with ``dispatch_id`` and ``agent_identity``.
    Raises ``TimeoutError`` if the agent does not appear in ``timeout_seconds``.
    """
    lkapi = LiveKitAPI(livekit_url, api_key, api_secret)
    try:
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            _build_dispatch_request(
                tenant_id=tenant_id, room=room, agent_name=agent_name
            )
        )

        deadline = time.monotonic() + timeout_seconds
        agent_identity: str | None = None
        while time.monotonic() < deadline:
            participants = await lkapi.room.list_participants(
                ListParticipantsRequest(room=room)
            )
            for p in participants.participants:
                if getattr(p, "kind", None) == _PARTICIPANT_KIND_AGENT:
                    agent_identity = p.identity
                    break
            if agent_identity is not None:
                break
            await asyncio.sleep(poll_interval)

        if agent_identity is None:
            raise TimeoutError(
                f"Agent did not join room {room!r} within {timeout_seconds}s. "
                "Check agent worker logs on Railway."
            )

        return {"dispatch_id": dispatch.id, "agent_identity": agent_identity}
    finally:
        await lkapi.aclose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point — parse args, check env, run dispatch + wait."""
    args = _parse_args()
    livekit_url = _require_env("LIVEKIT_URL")
    api_key = _require_env("LIVEKIT_API_KEY")
    api_secret = _require_env("LIVEKIT_API_SECRET")

    room = args.room or f"test-room-{uuid.uuid4().hex[:8]}"
    operator_identity = f"operator-{uuid.uuid4().hex[:6]}"

    print(f"Dispatching agent={args.agent_name!r} room={room!r} tenant_id={args.tenant_id}")

    try:
        result = asyncio.run(
            dispatch_and_wait(
                livekit_url=livekit_url,
                api_key=api_key,
                api_secret=api_secret,
                tenant_id=args.tenant_id,
                room=room,
                agent_name=args.agent_name,
                timeout_seconds=args.timeout,
            )
        )
    except TimeoutError as exc:
        print(f"\nTIMEOUT: {exc}", file=sys.stderr)
        sys.exit(3)
    except Exception as exc:  # noqa: BLE001 — script boundary: surface any server error
        print(f"\nLIVEKIT ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    token = _generate_participant_token(
        api_key=api_key,
        api_secret=api_secret,
        room=room,
        identity=operator_identity,
    )

    print(f"\nDispatch ID:     {result['dispatch_id']}")
    print(f"Agent identity:  {result['agent_identity']}")
    print(f"Room:            {room}")
    print(f"Operator ident:  {operator_identity}")
    print("\nOpen the LiveKit Playground to join the room as the operator:")
    print(f"  https://agents-playground.livekit.io/#url={livekit_url}&token={token}")
    print("\nOK Dispatch succeeded and agent joined.")


if __name__ == "__main__":
    main()
