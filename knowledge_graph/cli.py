"""Local command line interface. The graph is selected by KG_ROOT before import."""

import argparse
import json
from dataclasses import asdict, is_dataclass

from knowledge_graph import loader
from knowledge_graph.approvers import (
    compute_pending_approvers,
    compute_required_approvers,
    owner_source,
)
from knowledge_graph.index import regenerate
from knowledge_graph.search import search_units
from knowledge_graph.validation import validate


def _print(value):
    print(json.dumps(value, indent=2, default=lambda v: asdict(v) if is_dataclass(v) else str(v)))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="kg", description="A Markdown knowledge graph")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate all records, links, and approvals")
    listing = commands.add_parser("list", help="List commitments (default: entitled)")
    listing.add_argument("--lifecycle", default="entitled")
    listing.add_argument("--tag")
    load = commands.add_parser("load", help="Load a commitment or reference by id")
    load.add_argument("id")
    search = commands.add_parser("search", help="Search candidates and entitled commitments")
    search.add_argument("query")
    search.add_argument("--domains", nargs="*")
    search.add_argument("--limit", type=int, default=10)
    index = commands.add_parser("index", help="Regenerate knowledge catalogs")
    index.add_argument("--check", action="store_true")
    graph = commands.add_parser("graph", help="Inspect edges and license chains")
    graph.add_argument("id")
    graph.add_argument("--depth", type=int, default=3)
    review = commands.add_parser("review", help="Show candidates and pending validators")
    review.add_argument("--by")
    approve = commands.add_parser("approve", help="Record a human's capture validation")
    approve.add_argument("ids", nargs="+")
    approve.add_argument("--by", required=True)
    approve.add_argument("--source", required=True)
    ripple = commands.add_parser("ripple", help="Find related records and stale text after an edit")
    ripple.add_argument("id")
    ripple.add_argument("--removed", nargs="*", default=[])
    commands.add_parser("questions", help="List questions")
    commands.add_parser("ideas", help="List ideas")
    commands.add_parser("standing", help="List authority records")
    commands.add_parser("challenges", help="List challenges; mutations use the challenges module")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            report = validate()
            _print(report)
            return int(bool(report.errors))
        if args.command == "list":
            _print(loader.list_units(lifecycle=args.lifecycle, tag=args.tag))
        elif args.command == "load":
            _print(loader.load(args.id))
        elif args.command == "search":
            _print(search_units(args.query, domains=args.domains, max_results=max(0, args.limit)))
        elif args.command == "index":
            report = validate()
            if report.errors:
                _print(report)
                return 1
            drift = regenerate(args.check)
            _print({"changed": drift, "check": args.check})
            return int(args.check and bool(drift))
        elif args.command == "graph":
            _print(
                {
                    "edges": loader.find_edges(args.id),
                    "license_chains": loader.traverse_licenses(args.id, args.depth),
                }
            )
        elif args.command == "review":
            output = []
            for unit in loader.list_units(lifecycle="candidate", needs_approval_from=args.by):
                required = compute_required_approvers(unit)
                output.append(
                    {
                        "id": unit.id,
                        "subject": unit.subject,
                        "required": required,
                        "pending": compute_pending_approvers(unit, required),
                        "owner_source": owner_source(unit),
                    }
                )
            _print(output)
        elif args.command == "approve":
            from knowledge_graph.entitle import record_approvals

            report = validate()
            if report.errors:
                _print(report)
                return 1
            summary = record_approvals(
                [{"atom_id": uid, "by": args.by, "source": args.source} for uid in args.ids]
            )
            _print(summary)
            return int(any(not entry.recorded for entry in summary.entries))
        elif args.command == "ripple":
            from knowledge_graph.ripple import find_ripples

            _print(find_ripples(args.id, args.removed))
        elif args.command == "questions":
            from knowledge_graph.questions import list_questions

            _print(list_questions())
        elif args.command == "ideas":
            from knowledge_graph.ideas import list_ideas

            _print(list_ideas())
        elif args.command == "standing":
            from knowledge_graph.standing import list_standings

            _print(list_standings())
        elif args.command == "challenges":
            from knowledge_graph.challenges import list_challenges

            _print(list_challenges())
    except (ValueError, FileNotFoundError, PermissionError) as exc:
        parser.exit(1, f"kg: {exc}\n")
    return 0
