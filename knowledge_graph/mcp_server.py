"""Optional local stdio MCP access. All exposed tools are read-only."""

import json
from dataclasses import asdict, is_dataclass

from mcp.server.fastmcp import FastMCP

from knowledge_graph import loader
from knowledge_graph.approvers import compute_pending_approvers, compute_required_approvers
from knowledge_graph.challenges import list_challenges
from knowledge_graph.ideas import list_ideas
from knowledge_graph.questions import list_questions
from knowledge_graph.ripple import find_ripples
from knowledge_graph.search import search_units
from knowledge_graph.standing import list_standings

mcp = FastMCP("knowledge-graph-starter")


def _json(value):
    return json.dumps(value, default=lambda v: asdict(v) if is_dataclass(v) else str(v))


@mcp.tool()
def kg_search(query: str, limit: int = 10) -> str:
    """Search entitled and candidate records. Results include their lifecycle."""
    return _json(search_units(query, max_results=max(0, min(limit, 100))))


@mcp.tool()
def kg_load(atom_id: str) -> str:
    """Load one commitment or reference, including its provenance and lifecycle."""
    unit = loader.load(atom_id)
    return _json({"unit": unit, "challenges": list_challenges(challenged_atom=atom_id)})


@mcp.tool()
def kg_list(lifecycle: str = "entitled", tag: str | None = None) -> str:
    """List commitments, defaulting to entitled records."""
    return _json(loader.list_units(lifecycle=lifecycle, tag=tag))


@mcp.tool()
def kg_graph(atom_id: str, depth: int = 3) -> str:
    """Return incoming/outgoing edges and cycle-safe license chains."""
    return _json(
        {
            "edges": loader.find_edges(atom_id),
            "chains": loader.traverse_licenses(atom_id, max(0, min(depth, 10))),
        }
    )


@mcp.tool()
def kg_review_queue() -> str:
    """List candidates with their required and pending human validators."""
    output = []
    for unit in loader.list_units(lifecycle="candidate"):
        required = compute_required_approvers(unit)
        output.append(
            {
                "id": unit.id,
                "subject": unit.subject,
                "required": required,
                "pending": compute_pending_approvers(unit, required),
            }
        )
    return _json(output)


@mcp.tool()
def kg_standing() -> str:
    """List explicitly declared authority records."""
    return _json(list_standings())


@mcp.tool()
def kg_questions() -> str:
    """List questions, answers, and resolution status."""
    return _json(list_questions())


@mcp.tool()
def kg_ideas() -> str:
    """List ideas that have not yet become commitments, with status."""
    return _json(list_ideas())


@mcp.tool()
def kg_challenges(atom_id: str | None = None) -> str:
    """List challenges and their deliberation histories."""
    return _json(list_challenges(challenged_atom=atom_id))


@mcp.tool()
def kg_ripple(atom_id: str, removed_fragments: list[str]) -> str:
    """Find records potentially affected by a changed claim; human review is needed."""
    return _json(find_ripples(atom_id, removed_fragments))


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
