"""Record human approvals and promote candidates when their validators are satisfied."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import frontmatter
from knowledge_graph.config import safe_path
from knowledge_graph.approvers import compute_pending_approvers, compute_required_approvers
from knowledge_graph.loader import load, KNOWLEDGE_ROOT as _DEFAULT_ROOT

KNOWLEDGE_ROOT = _DEFAULT_ROOT


@dataclass
class EntryResult:
    atom_id: str
    recorded: bool
    flipped: bool
    pending_after: list[str] | None = None
    note: str = ""


@dataclass
class Summary:
    entries: list[EntryResult] = field(default_factory=list)

    def flipped_ids(self) -> list[str]:
        return [e.atom_id for e in self.entries if e.flipped]


def _today_iso() -> str:
    return date.today().isoformat()


def _load_path(atom_id: str) -> Path:
    return safe_path(KNOWLEDGE_ROOT, atom_id)


def _append_log(line: str) -> None:
    log_path = KNOWLEDGE_ROOT / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing = log_path.read_text() if log_path.exists() else ""
    log_path.write_text(existing + line + "\n")


def _build_record(batch_entry: dict) -> dict:
    if not isinstance(batch_entry.get("source"), str) or not batch_entry["source"].strip():
        raise ValueError("Approval source is required")
    date.fromisoformat(str(batch_entry.get("at") or _today_iso()))
    record: dict = {
        "by": batch_entry["by"],
        "at": batch_entry.get("at") or _today_iso(),
        "source": batch_entry["source"],
    }
    if batch_entry.get("relayed_by"):
        record["relayed_by"] = batch_entry["relayed_by"]
    if batch_entry.get("relay_note"):
        record["relay_note"] = batch_entry["relay_note"]
    if batch_entry.get("via"):
        record["via"] = batch_entry["via"]
    return record


def record_approvals(batch: list[dict]) -> Summary:
    summary = Summary()
    for entry in batch:
        atom_id = entry["atom_id"]
        path = _load_path(atom_id)
        if not path.exists():
            summary.entries.append(
                EntryResult(
                    atom_id=atom_id, recorded=False, flipped=False, note=f"atom not found at {path}"
                )
            )
            continue
        probe = load(atom_id)
        if probe.lifecycle is None or probe.lifecycle.value != "candidate":
            summary.entries.append(
                EntryResult(
                    atom_id=atom_id,
                    recorded=False,
                    flipped=False,
                    note=f"{atom_id} is not a candidate (lifecycle={probe.lifecycle}); skipping",
                )
            )
            continue
        required_now = compute_required_approvers(probe)
        if required_now is None:
            summary.entries.append(
                EntryResult(
                    atom_id=atom_id,
                    recorded=False,
                    flipped=False,
                    note=f"{atom_id} is legibility_ceiling; approvals do not apply",
                )
            )
            continue
        approver_name = entry["by"].strip().lower()
        required_lower = {r.lower() for r in required_now}
        if approver_name not in required_lower:
            summary.entries.append(
                EntryResult(
                    atom_id=atom_id,
                    recorded=False,
                    flipped=False,
                    note=f"{entry['by']} is not in required approvers {required_now} for {atom_id}",
                )
            )
            continue
        post = frontmatter.load(path)
        record = _build_record(entry)
        existing = post.metadata.get("approvals") or []
        if any(((e.get("by") or "").strip().lower() == approver_name for e in existing)):
            summary.entries.append(
                EntryResult(
                    atom_id=atom_id,
                    recorded=False,
                    flipped=False,
                    pending_after=None,
                    note=f"{entry['by']} has already approved {atom_id}; noop",
                )
            )
            continue
        post.metadata["approvals"] = existing + [record]
        path.write_text(frontmatter.dumps(post) + "\n")
        unit = load(atom_id)
        required = compute_required_approvers(unit)
        pending = compute_pending_approvers(unit, required)
        flipped = False
        if required and pending == [] and unit.lifecycle.value == "candidate":
            post = frontmatter.load(path)
            post.metadata["lifecycle"] = "entitled"
            path.write_text(frontmatter.dumps(post) + "\n")
            _append_log(
                f"## [{_today_iso()}] entitle | {atom_id} lifecycle candidate → entitled (all required approvers present)"
            )
            flipped = True
        summary.entries.append(
            EntryResult(atom_id=atom_id, recorded=True, flipped=flipped, pending_after=pending)
        )
    return summary


def reconcile_entitlements() -> Summary:
    from knowledge_graph.loader import list_units

    summary = Summary()
    for probe in list_units(lifecycle="candidate"):
        required = compute_required_approvers(probe)
        if not required:
            continue
        if compute_pending_approvers(probe, required) != []:
            continue
        path = _load_path(probe.id)
        post = frontmatter.load(path)
        if post.metadata.get("lifecycle") != "candidate":
            continue
        post.metadata["lifecycle"] = "entitled"
        path.write_text(frontmatter.dumps(post) + "\n")
        _append_log(
            f"## [{_today_iso()}] reconcile-entitle | {probe.id} lifecycle candidate → entitled (required {required} already satisfied under meeting-owner model)"
        )
        summary.entries.append(
            EntryResult(atom_id=probe.id, recorded=False, flipped=True, pending_after=[])
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="entitle")
    parser.add_argument("--approver", help="Name of the approver")
    parser.add_argument("--ids", help="Comma-separated atom ids")
    parser.add_argument("--source", help="Source path (meeting-notes/...)")
    parser.add_argument("--at", default=None, help="Approval date (YYYY-MM-DD); defaults to today")
    parser.add_argument("--relayed-by", default=None, help="Name of person relaying, if applicable")
    parser.add_argument("--relay-note", default=None, help="Verbatim relay phrase")
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Sweep all candidates and flip any whose required validator is already satisfied (no new approval recorded). Use after a model/standing change.",
    )
    args = parser.parse_args(argv)
    if args.reconcile:
        summary = reconcile_entitlements()
        flipped = summary.flipped_ids()
        for atom_id in flipped:
            print(f"[FLIP] {atom_id}")
        print(f"reconcile: {len(flipped)} candidate(s) flipped to entitled")
        return 0
    if not (args.approver and args.ids and args.source):
        parser.error("--approver, --ids, and --source are required unless --reconcile is used")
    atom_ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    batch = [
        {
            "atom_id": atom_id,
            "by": args.approver,
            "source": args.source,
            **({"at": args.at} if args.at else {}),
            **({"relayed_by": args.relayed_by} if args.relayed_by else {}),
            **({"relay_note": args.relay_note} if args.relay_note else {}),
        }
        for atom_id in atom_ids
    ]
    summary = record_approvals(batch)
    for entry in summary.entries:
        status = "FLIP" if entry.flipped else "ok" if entry.recorded else "skip"
        pending = "" if entry.pending_after is None else f"pending={entry.pending_after}"
        note = f" ({entry.note})" if entry.note else ""
        print(f"[{status}] {entry.atom_id} {pending}{note}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
