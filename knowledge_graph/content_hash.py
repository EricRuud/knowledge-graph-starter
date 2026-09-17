"""Compute a stable SHA-256 hash of a commitment subject and structured value."""

from __future__ import annotations
import hashlib
import json
from typing import Any


def commitment_content_hash(unit: Any) -> str:
    payload = json.dumps(
        {"subject": unit.subject, "value": unit.value},
        sort_keys=True,
        default=str,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
