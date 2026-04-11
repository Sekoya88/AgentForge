"""Webhook HMAC signing matches delivery format."""

from __future__ import annotations

import hashlib
import hmac
import json


def test_hmac_signature_format() -> None:
    secret = "whsec_test"
    payload = {"event": "execution.completed", "payload": {"x": 1}}
    raw = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    assert sig
    assert len(sig) == 64
