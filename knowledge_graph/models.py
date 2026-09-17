"""Data structures for commitments, lifecycle, entitlement, and inference edges."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class Kind(str, Enum):
    FACT = "fact"
    DECISION = "decision"


class Lifecycle(str, Enum):
    CANDIDATE = "candidate"
    ENTITLED = "entitled"
    SUPERSEDED = "superseded"


@dataclass
class Entitlement:
    measurability: str | None = None
    consequence: str | None = None


@dataclass
class InferenceEdge:
    target: str
    reason: str
    proposed_by: str
    validated: date | None = None


@dataclass
class Unit:
    id: str
    kind: Kind
    subject: str
    value: Any
    source: dict[str, Any]
    recorded_at: date
    lifecycle: Lifecycle | None
    authored_by: str | list[str] | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    overdue: bool = False
    confidence: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    references: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    entitlement: Entitlement | None = None
    accountable: str | None = None
    authority: str | None = None
    incompatible_with: list[str] = field(default_factory=list)
    licenses: list[InferenceEdge] = field(default_factory=list)
    precludes: list[InferenceEdge] = field(default_factory=list)
    reaffirmed: list[dict[str, Any]] = field(default_factory=list)
    revisions: list[dict[str, Any]] = field(default_factory=list)
    review_scores: dict[str, int] | None = None
    commitment_ease: int | None = None
    commitment_type: str | None = None
    atom_type: str = "commitment"
    review_summary: str | None = None
    cowork_summary: str | None = None
    legibility_ceiling: bool = False
    is_projection: bool = False
    projection_source: str | None = None
    projection_query: str | None = None
    requires_approval_from: list[str] | None = None
    approvals: list[dict[str, Any]] = field(default_factory=list)
    review_hold: bool = False
    rejected_at: date | None = None
    rejected_by: str | None = None
    rejection_note: str | None = None
    rejection_source: str | None = None
    body: str = ""

    def __post_init__(self) -> None:
        if self.valid_from is None:
            self.valid_from = self.recorded_at
