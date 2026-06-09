"""Firebase Cloud Messaging client (spike push).

`FakeFcmClient` records pushes in memory so the spike test can assert exactly one
push fired per spike event. `RealFcmClient` is the live wiring point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger("clients.fcm")


@dataclass
class PushMessage:
    politician_id: int
    title: str
    body: str
    dedupe_key: str


class FcmClient(Protocol):
    def send(self, msg: PushMessage) -> bool: ...


class FakeFcmClient:
    """In-memory FCM used by tests + offline mode. Inspect ``.sent``."""

    def __init__(self) -> None:
        self.sent: list[PushMessage] = []

    def send(self, msg: PushMessage) -> bool:
        self.sent.append(msg)
        log.info("fcm_fake_push", politician_id=msg.politician_id, dedupe_key=msg.dedupe_key)
        return True


class RealFcmClient:
    """Live FCM client (HTTP v1). Wired once FCM_SERVICE_ACCOUNT_JSON is provided."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, msg: PushMessage) -> bool:
        raise NotImplementedError(
            "RealFcmClient needs FCM_SERVICE_ACCOUNT_JSON + device tokens (WP5 live)."
        )


# Process-wide Fake instance so demo-mode pushes are inspectable across a run.
_FAKE_SINGLETON = FakeFcmClient()


def get_fcm_client(settings: Settings | None = None) -> FcmClient:
    settings = settings or get_settings()
    if settings.use_fake_clients:
        return _FAKE_SINGLETON
    return RealFcmClient(settings)
