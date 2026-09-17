"""Create, deliberate, and resolve challenges to commitments."""

from __future__ import annotations
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from datetime import date as _date
from enum import Enum
from pathlib import Path
from typing import Any
import frontmatter
from knowledge_graph.loader import KNOWLEDGE_ROOT
from knowledge_graph.config import KNOWLEDGE_ROOT as _ROOT, safe_path

CHALLENGES_ROOT = _ROOT / "challenges"


class ChallengeStatus(str, Enum):
    OPEN = "open"
    PROPOSED = "proposed"
    RESOLVED_ACCEPTED = "resolved-accepted"
    RESOLVED_REJECTED = "resolved-rejected"
    WITHDRAWN = "withdrawn"


class ChallengeBasis(str, Enum):
    DISAGREEMENT = "disagreement"
    AMBIGUITY = "ambiguity"
    INCOMPLETE_INFO = "incomplete-info"
    MULTI_STAKEHOLDER_ALIGNMENT = "multi-stakeholder-alignment"
    STALE_NEEDS_INVESTIGATION = "stale-needs-investigation"


@dataclass
class DeliberationEntry:
    date: date
    by: str
    contribution: str
    source: str | None = None


@dataclass
class Challenge:
    id: str
    challenges: list[str]
    basis: ChallengeBasis
    status: ChallengeStatus
    raised_by: str
    raised_at: date
    success_criteria: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    proposed_superseding_commitment: dict[str, Any] | None = None
    deliberation_log: list[DeliberationEntry] = field(default_factory=list)
    spawned_questions: list[str] = field(default_factory=list)
    affected_atoms: list[str] = field(default_factory=list)
    resolved_at: date | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None
    tags: list[str] = field(default_factory=list)
    body: str = ""


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


def _parse_deliberation(raw: list[dict] | None) -> list[DeliberationEntry]:
    if not raw:
        return []
    out: list[DeliberationEntry] = []
    for item in raw:
        out.append(
            DeliberationEntry(
                date=_parse_date(item.get("date")),
                by=item.get("by", ""),
                contribution=item.get("contribution", ""),
                source=item.get("source"),
            )
        )
    return out


def _challenge_from_post(post: frontmatter.Post, challenge_id: str) -> Challenge:
    md = post.metadata
    return Challenge(
        id=md.get("id", challenge_id),
        challenges=list(md.get("challenges") or []),
        basis=ChallengeBasis(md["basis"]),
        status=ChallengeStatus(md["status"]),
        raised_by=md["raised_by"],
        raised_at=_parse_date(md["raised_at"]),
        success_criteria=list(md.get("success_criteria") or []),
        blockers=list(md.get("blockers") or []),
        proposed_superseding_commitment=md.get("proposed_superseding_commitment"),
        deliberation_log=_parse_deliberation(md.get("deliberation_log")),
        spawned_questions=list(md.get("spawned_questions") or []),
        affected_atoms=list(md.get("affected_atoms") or []),
        resolved_at=_parse_date(md.get("resolved_at")),
        resolved_by=md.get("resolved_by"),
        resolution_note=md.get("resolution_note"),
        tags=list(md.get("tags") or []),
        body=post.content,
    )


def load_challenge(challenge_id: str) -> Challenge:
    path = safe_path(CHALLENGES_ROOT, challenge_id)
    if not path.exists():
        raise FileNotFoundError(f"Challenge not found: {challenge_id} (looked at {path})")
    post = frontmatter.load(safe_path(CHALLENGES_ROOT, path.stem))
    return _challenge_from_post(post, challenge_id)


def list_challenges(
    *, status: str | None = None, challenged_atom: str | None = None
) -> list[Challenge]:
    results: list[Challenge] = []
    for path in sorted(CHALLENGES_ROOT.glob("*.md")):
        if path.name.startswith(".") or path.name == "README.md":
            continue
        try:
            post = frontmatter.load(safe_path(CHALLENGES_ROOT, path.stem))
            if "basis" not in post.metadata or "status" not in post.metadata:
                continue
            ch = _challenge_from_post(post, path.stem)
        except Exception:
            continue
        if status is not None and ch.status.value != status:
            continue
        if challenged_atom is not None and challenged_atom not in ch.challenges:
            continue
        results.append(ch)
    return results


def find_open_challenges() -> list[Challenge]:
    return [
        c for c in list_challenges() if c.status in (ChallengeStatus.OPEN, ChallengeStatus.PROPOSED)
    ]


def _today() -> date:
    return _date.today()


def _today_iso() -> str:
    return _today().isoformat()


def _append_log(line: str) -> None:
    log_path = KNOWLEDGE_ROOT / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing = log_path.read_text() if log_path.exists() else ""
    log_path.write_text(existing + line + "\n")


def _assert_atoms_exist(atom_ids: list[str]) -> None:
    missing = [aid for aid in atom_ids if not safe_path(KNOWLEDGE_ROOT, aid).exists()]
    if missing:
        raise ValueError(f"Cannot challenge non-existent atoms: {missing}")


_SLUG_RE = re.compile("^[a-z0-9]+(-[a-z0-9]+)*$")


def _validate_challenge_id(challenge_id: str) -> None:
    if not challenge_id:
        raise ValueError("Challenge id cannot be empty")
    if not _SLUG_RE.match(challenge_id):
        raise ValueError(
            f"Invalid challenge id {challenge_id!r}: must be lowercase alphanumeric with hyphens only (kebab-case); no underscores, uppercase, spaces, or leading/trailing hyphens"
        )
    if safe_path(CHALLENGES_ROOT, challenge_id).exists():
        raise ValueError(
            f"Challenge id {challenge_id!r} already exists at knowledge/challenges/{challenge_id}.md"
        )
    if safe_path(KNOWLEDGE_ROOT, challenge_id).exists():
        raise ValueError(
            f"Challenge id {challenge_id!r} collides with existing commitment atom at knowledge/{challenge_id}.md — pick a distinct slug"
        )


_VALID_BASES = {b.value for b in ChallengeBasis}


def _load_post(challenge_id: str) -> tuple[Path, frontmatter.Post]:
    path = safe_path(CHALLENGES_ROOT, challenge_id)
    if not path.exists():
        raise FileNotFoundError(f"Challenge not found: {challenge_id}")
    return (path, frontmatter.load(path))


def append_deliberation(
    challenge_id: str,
    *,
    by: str,
    contribution: str,
    source: str | None = None,
    at: date | None = None,
    proposed_superseding_commitment: dict | None = None,
    add_blockers: list[str] | None = None,
    clear_blockers: list[str] | None = None,
    add_success_criteria: list[str] | None = None,
    add_affected_atoms: list[str] | None = None,
    add_spawned_questions: list[str] | None = None,
) -> None:
    path, post = _load_post(challenge_id)
    md = post.metadata
    if md.get("status") not in {"open", "proposed"}:
        raise ValueError("Cannot deliberate a resolved challenge")
    entry = {"date": (at or _today()).isoformat(), "by": by, "contribution": contribution}
    if source:
        entry["source"] = source
    log: list = list(md.get("deliberation_log") or [])
    log.append(entry)
    md["deliberation_log"] = log
    if proposed_superseding_commitment is not None:
        was_null = md.get("proposed_superseding_commitment") is None
        md["proposed_superseding_commitment"] = proposed_superseding_commitment
        if was_null and md.get("status") == "open":
            md["status"] = "proposed"
    if add_blockers:
        md["blockers"] = list(md.get("blockers") or []) + list(add_blockers)
    if clear_blockers:
        existing = list(md.get("blockers") or [])
        md["blockers"] = [b for b in existing if b not in set(clear_blockers)]
    if add_success_criteria:
        md["success_criteria"] = list(md.get("success_criteria") or []) + list(add_success_criteria)
    if add_affected_atoms:
        md["affected_atoms"] = list(md.get("affected_atoms") or []) + list(add_affected_atoms)
    if add_spawned_questions:
        md["spawned_questions"] = list(md.get("spawned_questions") or []) + list(
            add_spawned_questions
        )
    path.write_text(frontmatter.dumps(post) + "\n")
    _append_log(f"## {_today_iso()} deliberate-challenge | {challenge_id} by {by}")


def create_challenge(
    *,
    id: str,
    challenges: list[str],
    basis: str,
    raised_by: str,
    success_criteria: list[str],
    proposed_superseding_commitment: dict | None = None,
    blockers: list[str] | None = None,
    affected_atoms: list[str] | None = None,
    tags: list[str] | None = None,
    raised_at: date | None = None,
    body: str = "",
) -> str:
    _validate_challenge_id(id)
    if basis not in _VALID_BASES:
        raise ValueError(f"Invalid basis {basis!r}; must be one of {sorted(_VALID_BASES)}")
    if not challenges:
        raise ValueError("challenges list cannot be empty")
    _assert_atoms_exist(challenges)
    ch_id = id
    raised_at = raised_at or _today()
    status = "proposed" if proposed_superseding_commitment else "open"
    metadata = {
        "id": ch_id,
        "challenges": list(challenges),
        "basis": basis,
        "success_criteria": list(success_criteria),
        "proposed_superseding_commitment": proposed_superseding_commitment,
        "raised_by": raised_by,
        "raised_at": raised_at.isoformat(),
        "status": status,
        "blockers": list(blockers or []),
        "deliberation_log": [],
        "spawned_questions": [],
        "affected_atoms": list(affected_atoms or []),
        "resolved_at": None,
        "resolved_by": None,
        "resolution_note": None,
        "tags": list(tags or []),
    }
    post = frontmatter.Post(body, **metadata)
    CHALLENGES_ROOT.mkdir(parents=True, exist_ok=True)
    safe_path(CHALLENGES_ROOT, ch_id).write_text(frontmatter.dumps(post) + "\n")
    for atom_id in challenges:
        _add_challenge_backpointer(atom_id=atom_id, challenge_id=ch_id, raised_by=raised_by)
    _append_log(
        f"## {_today_iso()} raise-challenge | {ch_id} raised against {','.join(challenges)} by {raised_by} (basis: {basis})"
    )
    return ch_id


def _add_challenge_backpointer(*, atom_id: str, challenge_id: str, raised_by: str) -> None:
    path = safe_path(KNOWLEDGE_ROOT, atom_id)
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    note = f"\n\n> **Open challenge:** `{challenge_id}` (raised by {raised_by}, {_today_iso()}) holds this commitment open for deliberation — see `knowledge/challenges/{challenge_id}.md` before acting on this atom."
    if note.strip() in text:
        return
    match = re.search("^# .*$", text, re.MULTILINE)
    if match is None:
        return
    updated = text[: match.end()] + note + text[match.end() :]
    path.write_text(updated, encoding="utf-8")


def _append_reaffirmed_entry(*, atom_id: str, by: str, note: str) -> None:
    atom_path = safe_path(KNOWLEDGE_ROOT, atom_id)
    if not atom_path.exists():
        raise FileNotFoundError(f"Cannot reaffirm missing atom: {atom_id}")
    post = frontmatter.load(atom_path)
    md = post.metadata
    reaffirmed = list(md.get("reaffirmed") or [])
    reaffirmed.append({"date": _today_iso(), "by": by, "note": note})
    md["reaffirmed"] = reaffirmed
    atom_path.write_text(frontmatter.dumps(post) + "\n")


def _retire_atom(*, atom_id: str, via_challenge: str) -> None:
    atom_path = safe_path(KNOWLEDGE_ROOT, atom_id)
    if not atom_path.exists():
        raise FileNotFoundError(f"Cannot retire missing atom: {atom_id}")
    post = frontmatter.load(atom_path)
    post.metadata["lifecycle"] = "superseded"
    post.metadata["superseded_by"] = None
    post.metadata.setdefault("retired_via", via_challenge)
    atom_path.write_text(frontmatter.dumps(post) + "\n")


_REQUIRED_SUPERSEDING_FIELDS = ("id", "commitment_type", "subject", "value")


def _materialize_superseding_atom(
    *, superseding: dict, supersedes_ids: list[str], via_challenge: str
) -> str:
    missing = [
        f for f in _REQUIRED_SUPERSEDING_FIELDS if f not in superseding or superseding[f] is None
    ]
    if missing:
        raise ValueError(f"proposed_superseding_commitment missing required fields: {missing}")
    new_id = superseding["id"]
    if not _SLUG_RE.fullmatch(new_id):
        raise ValueError("Replacement id must be a root-level kebab-case slug")
    new_path = safe_path(KNOWLEDGE_ROOT, new_id)
    if new_path.exists():
        raise ValueError(f"Atom id {new_id} already exists — pick a different slug")
    body = superseding.get("body", "")
    primary_supersedes = supersedes_ids[0] if supersedes_ids else None
    metadata = dict(superseding)
    metadata.pop("body", None)
    metadata["id"] = new_id
    metadata.pop("kind", None)
    metadata["approvals"] = []
    if superseding["commitment_type"] not in {"FACT", "POLICY", "BOTH"}:
        raise ValueError("Replacement commitment_type must be FACT, POLICY, or BOTH")
    metadata["subject"] = superseding["subject"]
    metadata["value"] = superseding["value"]
    metadata["lifecycle"] = "candidate"
    metadata["source"] = {
        "type": "challenge-resolution",
        "reference": via_challenge,
        "date": _today_iso(),
    }
    metadata["recorded_at"] = _today_iso()
    metadata["supersedes"] = primary_supersedes
    metadata["tags"] = list(superseding.get("tags") or [])
    if len(supersedes_ids) > 1:
        metadata["also_supersedes"] = supersedes_ids[1:]
    post = frontmatter.Post(body, **metadata)
    new_path.write_text(frontmatter.dumps(post) + "\n")
    return new_id


def _mark_superseded(*, atom_id: str, new_id: str) -> None:
    atom_path = safe_path(KNOWLEDGE_ROOT, atom_id)
    if not atom_path.exists():
        raise FileNotFoundError(f"Cannot supersede missing atom: {atom_id}")
    post = frontmatter.load(atom_path)
    post.metadata["lifecycle"] = "superseded"
    post.metadata["superseded_by"] = new_id
    atom_path.write_text(frontmatter.dumps(post) + "\n")


_VALID_RESOLUTIONS = {"accepted", "rejected", "withdrawn"}


def resolve_challenge(
    challenge_id: str, *, by: str, resolution: str, note: str | None = None
) -> None:
    if resolution not in _VALID_RESOLUTIONS:
        raise ValueError(
            f"Invalid resolution {resolution!r}; must be one of {sorted(_VALID_RESOLUTIONS)}"
        )
    path, post = _load_post(challenge_id)
    md = post.metadata
    if md.get("status") in ("resolved-accepted", "resolved-rejected", "withdrawn"):
        raise ValueError(f"Challenge {challenge_id} already resolved (status={md['status']})")
    if resolution == "withdrawn":
        if md.get("raised_by") != by:
            raise PermissionError(
                f"Only the raiser ({md.get('raised_by')}) can withdraw {challenge_id}"
            )
        md["status"] = "withdrawn"
        md["resolved_at"] = _today_iso()
        md["resolved_by"] = by
        md["resolution_note"] = note
        path.write_text(frontmatter.dumps(post) + "\n")
        _close_backpointers(md, challenge_id)
        _append_log(f"## {_today_iso()} resolve-challenge | {challenge_id} withdrawn by {by}")
        return
    if resolution == "rejected":
        for atom_id in md.get("challenges") or []:
            _append_reaffirmed_entry(
                atom_id=atom_id,
                by=by,
                note=f"Reaffirmed after {challenge_id} (rejected)" + (f": {note}" if note else ""),
            )
        md["status"] = "resolved-rejected"
        md["resolved_at"] = _today_iso()
        md["resolved_by"] = by
        md["resolution_note"] = note
        path.write_text(frontmatter.dumps(post) + "\n")
        _close_backpointers(md, challenge_id)
        _append_log(f"## {_today_iso()} resolve-challenge | {challenge_id} rejected by {by}")
        return
    if resolution == "accepted":
        superseding = md.get("proposed_superseding_commitment")
        if superseding is None:
            for atom_id in md.get("challenges") or []:
                _retire_atom(atom_id=atom_id, via_challenge=challenge_id)
            md["status"] = "resolved-accepted"
            md["resolved_at"] = _today_iso()
            md["resolved_by"] = by
            md["resolution_note"] = note
            path.write_text(frontmatter.dumps(post) + "\n")
            _close_backpointers(md, challenge_id)
            _append_log(
                f"## {_today_iso()} resolve-challenge | {challenge_id} accepted (retire) by {by}"
            )
            return
        new_id = _materialize_superseding_atom(
            superseding=superseding,
            supersedes_ids=list(md.get("challenges") or []),
            via_challenge=challenge_id,
        )
        for atom_id in md.get("challenges") or []:
            _mark_superseded(atom_id=atom_id, new_id=new_id)
        md["status"] = "resolved-accepted"
        md["resolved_at"] = _today_iso()
        md["resolved_by"] = by
        md["resolution_note"] = note
        path.write_text(frontmatter.dumps(post) + "\n")
        _close_backpointers(md, challenge_id)
        _append_log(
            f"## {_today_iso()} resolve-challenge | {challenge_id} accepted by {by} — materialized {new_id}"
        )
        return


def _cmd_raise(args: argparse.Namespace) -> int:
    superseding = None
    if args.superseding_json:
        superseding = json.loads(args.superseding_json)
    new_id = create_challenge(
        id=args.id,
        challenges=args.atoms,
        basis=args.basis,
        raised_by=args.raised_by,
        success_criteria=args.success_criterion or [],
        blockers=args.blocker or [],
        proposed_superseding_commitment=superseding,
        tags=args.tag or [],
    )
    print(new_id)
    return 0


def _cmd_deliberate(args: argparse.Namespace) -> int:
    superseding = None
    if args.superseding_json:
        superseding = json.loads(args.superseding_json)
    append_deliberation(
        args.challenge_id,
        by=args.by,
        contribution=args.contribution,
        source=args.source,
        proposed_superseding_commitment=superseding,
        add_blockers=args.add_blocker or None,
        clear_blockers=args.clear_blocker or None,
        add_success_criteria=args.add_success_criterion or None,
        add_affected_atoms=args.add_affected_atom or None,
        add_spawned_questions=args.add_spawned_question or None,
    )
    print(f"{args.challenge_id} updated")
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    resolve_challenge(args.challenge_id, by=args.by, resolution=args.resolution, note=args.note)
    print(f"{args.challenge_id} resolved as {args.resolution}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="challenges")
    sub = parser.add_subparsers(dest="cmd", required=True)
    raise_p = sub.add_parser("raise", help="Create a new challenge")
    raise_p.add_argument(
        "--id",
        required=True,
        help="Descriptive kebab-case slug id for this challenge (e.g. revisit-loan-period)",
    )
    raise_p.add_argument(
        "--atoms", nargs="+", required=True, help="Atom ids this challenge targets"
    )
    raise_p.add_argument("--basis", required=True, choices=sorted(_VALID_BASES))
    raise_p.add_argument("--raised-by", required=True)
    raise_p.add_argument("--success-criterion", action="append", default=[])
    raise_p.add_argument("--blocker", action="append", default=[])
    raise_p.add_argument("--tag", action="append", default=[])
    raise_p.add_argument(
        "--superseding-json", default=None, help="JSON dict for proposed_superseding_commitment"
    )
    raise_p.set_defaults(func=_cmd_raise)
    delib_p = sub.add_parser("deliberate", help="Append to deliberation log")
    delib_p.add_argument("challenge_id")
    delib_p.add_argument("--by", required=True)
    delib_p.add_argument("--contribution", required=True)
    delib_p.add_argument("--source", default=None)
    delib_p.add_argument("--superseding-json", default=None)
    delib_p.add_argument("--add-blocker", action="append", default=[])
    delib_p.add_argument("--clear-blocker", action="append", default=[])
    delib_p.add_argument("--add-success-criterion", action="append", default=[])
    delib_p.add_argument("--add-affected-atom", action="append", default=[])
    delib_p.add_argument("--add-spawned-question", action="append", default=[])
    delib_p.set_defaults(func=_cmd_deliberate)
    resolve_p = sub.add_parser("resolve", help="Resolve a challenge")
    resolve_p.add_argument("challenge_id")
    resolve_p.add_argument("--by", required=True)
    resolve_p.add_argument("--resolution", required=True, choices=sorted(_VALID_RESOLUTIONS))
    resolve_p.add_argument("--note", default=None)
    resolve_p.set_defaults(func=_cmd_resolve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def _close_backpointers(metadata: dict, challenge_id: str) -> None:
    for atom_id in metadata.get("challenges", []):
        path = safe_path(KNOWLEDGE_ROOT, atom_id)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        prefix = f"> **Open challenge:** `{challenge_id}` "
        lines = [
            f"> **Resolved challenge:** `{challenge_id}` ({metadata['status']})."
            if line.startswith(prefix)
            else line
            for line in lines
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
