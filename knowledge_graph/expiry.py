"""Derive overdue status without changing the recorded lifecycle."""

from __future__ import annotations
from dataclasses import replace
from datetime import date
from knowledge_graph.models import Lifecycle, Unit


def is_expired(unit: Unit, *, today: date | None = None) -> bool:
    if unit.valid_until is None:
        return False
    if today is None:
        today = date.today()
    return unit.valid_until < today


def apply_expiry(unit: Unit, *, today: date | None = None) -> Unit:
    if unit.lifecycle not in (Lifecycle.ENTITLED, Lifecycle.CANDIDATE):
        return unit
    if is_expired(unit, today=today):
        return replace(unit, overdue=True)
    return unit
