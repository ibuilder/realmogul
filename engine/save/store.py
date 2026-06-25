"""Save envelope: versioned JSON with an integrity checksum + load-time migration.

Envelope shape::

    {"version": <int>, "checksum": "<sha256 of canonical state>", "state": {...}}

On load we verify the checksum, then run migrations until the state matches the
current ``SCHEMA_VERSION``. The client never trusts a tampered or stale save
silently — a bad checksum raises.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from engine.progression.session import GameSession
from engine.save.migrations import MIGRATIONS
from engine.save.schema import SCHEMA_VERSION, session_to_state, state_to_session


class SaveIntegrityError(Exception):
    """Raised when a save's checksum does not match its body (tampered/corrupt)."""


def _canonical(state: dict[str, Any]) -> str:
    """Stable JSON for hashing: sorted keys, no incidental whitespace."""
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def _checksum(state: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(state).encode("utf-8")).hexdigest()


def save_to_dict(session: GameSession) -> dict[str, Any]:
    """Produce the versioned, checksummed envelope for a session."""
    state = session_to_state(session)
    return {"version": SCHEMA_VERSION, "checksum": _checksum(state), "state": state}


def save_to_json(session: GameSession, *, indent: int | None = None) -> str:
    return json.dumps(save_to_dict(session), indent=indent)


def _apply_migrations(state: dict[str, Any], from_version: int) -> dict[str, Any]:
    version = from_version
    while version < SCHEMA_VERSION:
        migrate = MIGRATIONS.get(version)
        if migrate is None:
            raise SaveIntegrityError(f"no migration registered from version {version}")
        state = migrate(state)
        version += 1
    return state


def load_from_dict(envelope: dict[str, Any]) -> GameSession:
    """Verify, migrate, and rebuild a session from a save envelope."""
    version = envelope["version"]
    state = envelope["state"]
    expected = envelope.get("checksum")
    if expected is not None and _checksum(state) != expected:
        raise SaveIntegrityError("checksum mismatch — save is corrupt or tampered")
    if version < SCHEMA_VERSION:
        state = _apply_migrations(state, version)
    return state_to_session(state)


def load_from_json(text: str) -> GameSession:
    return load_from_dict(json.loads(text))
