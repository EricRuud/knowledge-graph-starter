"""Load open questions and their eventual answers."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any
import frontmatter
from knowledge_graph.config import KNOWLEDGE_ROOT as _ROOT, safe_path

QUESTIONS_ROOT = _ROOT / "questions"


class QuestionStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


@dataclass
class Question:
    id: str
    question: str
    status: QuestionStatus
    owner: str | None = None
    blocks: str | None = None
    domains: list[str] = field(default_factory=list)
    recorded_at: date | None = None
    source: dict[str, Any] | None = None
    answer: str | None = None
    resolved_at: date | None = None
    resolved_by: str | None = None
    tags: list[str] = field(default_factory=list)
    body: str = ""
    licenses: list[dict] = field(default_factory=list)
    precludes: list[dict] = field(default_factory=list)


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date) and (not isinstance(val, datetime)):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val)
    raise ValueError(f"Cannot parse date from {val!r}")


def _question_from_frontmatter(post: frontmatter.Post, question_id: str) -> Question:
    md = post.metadata
    return Question(
        id=md.get("id", question_id),
        question=md["question"],
        status=QuestionStatus(md["status"]),
        owner=md.get("owner"),
        blocks=md.get("blocks"),
        domains=md.get("domains", []) or [],
        recorded_at=_parse_date(md.get("recorded_at")),
        source=md.get("source"),
        answer=md.get("answer"),
        resolved_at=_parse_date(md.get("resolved_at")),
        resolved_by=md.get("resolved_by"),
        tags=md.get("tags", []) or [],
        body=post.content,
        licenses=md.get("licenses", []) or [],
        precludes=md.get("precludes", []) or [],
    )


def load_question(question_id: str) -> Question:
    path = safe_path(QUESTIONS_ROOT, question_id)
    if not path.exists():
        raise FileNotFoundError(f"Question not found: {question_id} (looked at {path})")
    post = frontmatter.load(safe_path(QUESTIONS_ROOT, path.stem))
    return _question_from_frontmatter(post, question_id)


def list_questions(*, status: str | None = None, domain: str | None = None) -> list[Question]:
    questions: list[Question] = []
    for path in sorted(QUESTIONS_ROOT.glob("*.md")):
        if path.name.startswith(".") or path.name == "README.md":
            continue
        try:
            post = frontmatter.load(safe_path(QUESTIONS_ROOT, path.stem))
            if "question" not in post.metadata:
                continue
            q = _question_from_frontmatter(post, path.stem)
        except Exception:
            continue
        if status is not None and q.status.value != status:
            continue
        if domain is not None and domain not in q.domains:
            continue
        questions.append(q)
    return questions
