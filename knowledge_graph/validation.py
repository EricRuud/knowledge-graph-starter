"""Validate every record explicitly; malformed files must never disappear silently."""

from dataclasses import dataclass, field
from datetime import date

import frontmatter

from knowledge_graph import config, loader, standing
from knowledge_graph.approvers import compute_pending_approvers, compute_required_approvers
from knowledge_graph.challenges import _challenge_from_post
from knowledge_graph.ideas import _idea_from_frontmatter
from knowledge_graph.questions import _question_from_frontmatter


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    records: int = 0


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _strings(value, field_name):
    _require(
        isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value),
        f"{field_name} must be a list of nonempty strings",
    )


def _date(value):
    _require(value is not None, "date is required")
    date.fromisoformat(str(value))


def validate() -> Report:
    report = Report()
    units = {}
    subrecords = []
    root = loader.KNOWLEDGE_ROOT
    if not root.is_dir():
        report.errors.append("Knowledge directory does not exist; set KG_ROOT or run from the repo")
        return report
    try:
        settings = config.approval_settings()
    except (ValueError, TypeError) as exc:
        report.errors.append(f"_config.yaml: {exc}")
        settings = {"owner_priority": [], "fallback_owner": None}
    humans = set()
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if path.name in {"README.md", "index.md", "index-candidates.md", "log.md"}:
            continue
        try:
            _require(not path.is_symlink(), "symlinks are not supported in the graph")
            _require(path.resolve().is_relative_to(root.resolve()), "path escapes graph")
            post = frontmatter.load(path)
            md = post.metadata
            _require(bool(md), "YAML frontmatter is required")
            group = rel.parts[0] if len(rel.parts) > 1 else "commitments"
            record_id = rel.with_suffix("").as_posix() if group == "commitments" else path.stem
            config.safe_path(root, record_id)
            if group == "standing":
                record = standing._record_from_post(post)
                _require(bool(record.entity.strip()), "entity is required")
                _strings(md.get("domains", []), "domains")
                if record.type == "human":
                    key = record.entity.strip().casefold()
                    _require(key not in humans, "duplicate human entity")
                    humans.add(key)
            elif group in {"questions", "ideas", "challenges"}:
                _require(md.get("id") == record_id, "id must match filename")
                parser = {
                    "questions": _question_from_frontmatter,
                    "ideas": _idea_from_frontmatter,
                    "challenges": _challenge_from_post,
                }[group]
                record = parser(post, record_id)
                if group == "ideas":
                    _require(md.get("type") == "idea", "type must be idea")
                    _require(bool(record.subject), "subject is required")
                if group == "questions":
                    _require(bool(record.question), "question is required")
                    if record.status.value == "resolved":
                        _require(
                            bool(record.answer and record.resolved_by and record.resolved_at),
                            "resolved question needs answer, resolved_by, resolved_at",
                        )
                if group == "challenges":
                    _strings(md.get("challenges"), "challenges")
                    _require(bool(record.challenges), "challenges cannot be empty")
                    _require(bool(record.raised_by), "raised_by is required")
                    _date(record.raised_at)
                    if record.status.value in {
                        "resolved-accepted",
                        "resolved-rejected",
                        "withdrawn",
                    }:
                        _require(
                            bool(record.resolved_by and record.resolved_at),
                            "resolved challenge needs resolved_by and resolved_at",
                        )
                subrecords.append((group, record))
            elif group == "commitments":
                _require(md.get("id") == record_id, "id must match filename")
                _require(
                    isinstance(md.get("subject"), str) and bool(md["subject"].strip()),
                    "subject must be a nonempty string",
                )
                _require("value" in md, "value is required")
                _require(
                    md.get("atom_type", "commitment") in {"commitment", "reference"},
                    "atom_type must be commitment or reference",
                )
                _require(isinstance(md.get("source"), dict), "source must be a mapping")
                _require(
                    bool(md["source"].get("type") and md["source"].get("reference")),
                    "source needs type and reference",
                )
                _date(md["source"].get("date"))
                _date(md.get("recorded_at"))
                if md.get("atom_type", "commitment") == "commitment":
                    _require(
                        md.get("commitment_type") in {"FACT", "POLICY", "BOTH"},
                        "commitment_type must be FACT, POLICY, or BOTH",
                    )
                    _require(
                        md.get("lifecycle") in {"candidate", "entitled", "superseded"},
                        "lifecycle must be candidate, entitled, or superseded",
                    )
                for key in ("tags", "references", "incompatible_with"):
                    _strings(md.get(key, []), key)
                if "requires_approval_from" in md:
                    _strings(md["requires_approval_from"], "requires_approval_from")
                    _require(
                        bool(md["requires_approval_from"]), "requires_approval_from cannot be empty"
                    )
                for kind in ("licenses", "precludes"):
                    _require(isinstance(md.get(kind, []), list), f"{kind} must be a list")
                    for edge in md.get(kind, []):
                        _require(
                            isinstance(edge, dict)
                            and all(edge.get(k) for k in ("target", "reason", "proposed_by")),
                            f"{kind} needs target, reason, proposed_by",
                        )
                seen = set()
                _require(isinstance(md.get("approvals", []), list), "approvals must be a list")
                for approval in md.get("approvals", []):
                    _require(
                        isinstance(approval, dict)
                        and bool(approval.get("by") and approval.get("source")),
                        "approval needs by, at, source",
                    )
                    _date(approval.get("at"))
                    key = approval["by"].strip().casefold()
                    _require(key not in seen, "duplicate approval")
                    seen.add(key)
                units[record_id] = loader._unit_from_frontmatter(post, record_id)
            else:
                raise ValueError(f"Unknown substore: {group}")
            report.records += 1
        except Exception as exc:
            report.errors.append(f"{rel.as_posix()}: {exc}")

    for name in settings["owner_priority"] + (
        [settings["fallback_owner"]] if settings["fallback_owner"] else []
    ):
        if name.strip().casefold() not in humans:
            report.errors.append(f"Configured validator has no human standing record: {name}")
    for uid, unit in units.items():
        try:
            for target in (
                unit.references
                + unit.incompatible_with
                + [e.target for e in unit.licenses + unit.precludes]
            ):
                _require(target in units, f"missing commitment/reference target: {target}")
            for target in (unit.supersedes, unit.superseded_by):
                if target:
                    _require(target in units, f"missing supersession target: {target}")
            if unit.atom_type != "commitment":
                continue
            required = compute_required_approvers(unit)
            for name in required or []:
                _require(
                    name.strip().casefold() in humans, f"validator has no human standing: {name}"
                )
            if unit.lifecycle.value == "entitled" and not unit.legibility_ceiling:
                _require(bool(required), "entitled commitment has no resolved validator")
                _require(
                    not compute_pending_approvers(unit, required),
                    "entitled commitment lacks required approvals",
                )
            if required == []:
                report.warnings.append(
                    f"{uid}: validator unresolved; set source owner or requires_approval_from"
                )
            if (
                unit.valid_until
                and unit.valid_until < date.today()
                and unit.lifecycle.value != "superseded"
            ):
                report.warnings.append(
                    f"{uid}: overdue since {unit.valid_until}; lifecycle unchanged"
                )
            if unit.lifecycle.value == "entitled":
                for target in unit.incompatible_with + [e.target for e in unit.precludes]:
                    if units[target].lifecycle and units[target].lifecycle.value == "entitled":
                        report.errors.append(f"{uid}: conflicts with entitled commitment {target}")
        except Exception as exc:
            report.errors.append(f"{uid}: {exc}")
    for group, record in subrecords:
        targets = (
            record.challenges
            if group == "challenges"
            else record.promoted_to
            if group == "ideas"
            else []
        )
        for target in targets:
            if target not in units:
                report.errors.append(f"{group}/{record.id}: missing target {target}")
    return report
