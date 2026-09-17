from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import subprocess
import sys

import frontmatter
import pytest

from knowledge_graph import approvers, challenges, entitle, loader
from knowledge_graph.content_hash import commitment_content_hash
from knowledge_graph.expiry import apply_expiry
from knowledge_graph.ideas import list_ideas
from knowledge_graph.index import regenerate
from knowledge_graph.questions import list_questions
from knowledge_graph.ripple import find_ripples
from knowledge_graph.search import search_units
from knowledge_graph.standing import list_standings
from knowledge_graph.validation import validate


def edit(graph, atom_id, **changes):
    path = graph / f"{atom_id}.md"
    post = frontmatter.load(path)
    post.metadata.update(changes)
    path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


def approve(by="Demo Librarian"):
    return entitle.record_approvals(
        [{"atom_id": "return-reminder", "by": by, "source": "examples/library-review.md"}]
    )


def test_demo_validates_and_default_list_is_entitled(graph):
    assert validate().errors == []
    assert validate().records == 10
    assert {u.id for u in loader.list_units()} == {"standard-loan-period", "shelf-capacity"}
    assert loader.load("meeting-notes-index").atom_type == "reference"
    assert len(loader.list_units(lifecycle="all")) == 4


def test_search_and_substores(graph):
    assert search_units("loan period")[0]["id"] == "standard-loan-period"
    assert search_units("reminder")[0]["lifecycle"] == "candidate"
    assert search_units("loan period", domains=["unknown"]) == []
    assert list_questions()[0].id == "return-slot"
    assert list_ideas()[0].id == "seed-lending"
    assert len(list_standings()) == 2
    assert challenges.find_open_challenges()[0].id == "reminder-timing"
    with pytest.raises(ValueError):
        loader.load("questions/return-slot")


def test_source_owner_and_approval_flow(graph):
    unit = loader.load("return-reminder")
    assert approvers.compute_required_approvers(unit) == ["Demo Librarian"]
    assert approvers.owner_source(unit) == "explicit"
    assert not approve("Demo Coordinator").entries[0].recorded
    assert approve("demo librarian").flipped_ids() == ["return-reminder"]
    assert loader.load("return-reminder").lifecycle.value == "entitled"
    assert not approve().entries[0].recorded
    assert len(loader.load("return-reminder").approvals) == 1
    assert (graph / "log.md").exists()
    assert validate().errors == []


def test_multi_approver_override_and_relay(graph):
    edit(graph, "return-reminder", requires_approval_from=["Demo Librarian", "Demo Coordinator"])
    assert not approve().entries[0].flipped
    assert not approve("DEMO LIBRARIAN").entries[0].recorded
    result = entitle.record_approvals(
        [
            {
                "atom_id": "return-reminder",
                "by": "Demo Coordinator",
                "source": "examples/library-review.md",
                "relayed_by": "Demo Librarian",
                "relay_note": "Fictional relayed confirmation",
            }
        ]
    )
    assert result.flipped_ids() == ["return-reminder"]
    assert loader.load("return-reminder").approvals[-1]["relayed_by"] == "Demo Librarian"


def test_no_implicit_owner_and_no_empty_set_promotion(graph):
    edit(
        graph,
        "return-reminder",
        source={"type": "example", "reference": "unknown", "date": "2026-01-12"},
    )
    unit = loader.load("return-reminder")
    assert approvers.compute_required_approvers(unit) == []
    assert approvers.owner_source(unit) == "unresolved"
    assert not approve().entries[0].recorded
    assert entitle.reconcile_entitlements().flipped_ids() == []
    assert any("unresolved" in item for item in validate().warnings)
    edit(graph, "return-reminder", requires_approval_from=[])
    assert any("cannot be empty" in item for item in validate().errors)


def test_priority_and_fallback_are_configured(graph):
    index = frontmatter.load(graph / "meeting-notes-index.md")
    index["value"]["notes"][0].pop("owner")
    (graph / "meeting-notes-index.md").write_text(frontmatter.dumps(index))
    unit = loader.load("return-reminder")
    assert approvers.owner_source(unit) == "participants"
    (graph / "_config.yaml").write_text("owner_priority: []\nfallback_owner: Demo Coordinator\n")
    assert approvers.owner_source(unit) == "fallback"
    assert approvers.compute_required_approvers(unit) == ["Demo Coordinator"]


def test_approval_requires_evidence(graph):
    with pytest.raises(ValueError, match="source"):
        entitle.record_approvals(
            [{"atom_id": "return-reminder", "by": "Demo Librarian", "source": ""}]
        )
    assert loader.load("return-reminder").approvals == []


def test_expiry_is_derived_and_does_not_retire(graph):
    unit = replace(loader.load("standard-loan-period"), valid_until=date(2020, 1, 1))
    overdue = apply_expiry(unit, today=date(2020, 1, 2))
    assert overdue.overdue
    assert overdue.lifecycle.value == "entitled"
    assert not unit.overdue
    assert not apply_expiry(unit, today=date(2020, 1, 1)).overdue


def test_edges_traversal_cycles_and_conflicts(graph):
    assert loader.traverse_licenses("standard-loan-period") == [
        ["standard-loan-period", "return-reminder"]
    ]
    assert loader.traverse_licenses("standard-loan-period", max_depth=0) == []
    edit(
        graph,
        "return-reminder",
        licenses=[
            {
                "target": "standard-loan-period",
                "reason": "Fictional cycle",
                "proposed_by": "Demo Librarian",
            }
        ],
    )
    assert len(loader.traverse_licenses("standard-loan-period", max_depth=20)) == 1
    assert loader.find_edges("return-reminder")["incoming_licenses"][0][0] == "standard-loan-period"
    assert loader.edge_weight("entitled", "candidate") == "provisional"
    assert loader.edge_weight("entitled", "superseded") == "historical"
    edit(graph, "standard-loan-period", incompatible_with=["shelf-capacity"])
    assert loader.find_incompatibility_violations()
    assert any("conflicts" in err for err in validate().errors)


@pytest.mark.parametrize(
    "changes,fragment",
    [
        (
            {
                "licenses": [
                    {"target": "missing", "reason": "Example", "proposed_by": "Demo Librarian"}
                ]
            },
            "missing",
        ),
        ({"licenses": ["bad"]}, "needs target"),
        ({"id": "wrong"}, "id must match"),
        ({"approvals": []}, "lacks required approvals"),
        ({"requires_approval_from": ["Unknown Reviewer"]}, "no human standing"),
        ({"lifecycle": "invalid"}, "lifecycle"),
        ({"recorded_at": "yesterday"}, "isoformat"),
    ],
)
def test_validation_rejects_bad_records(graph, changes, fragment):
    edit(graph, "standard-loan-period", **changes)
    assert any(fragment in error for error in validate().errors)


def test_malformed_yaml_and_untyped_files_are_reported(graph):
    (graph / "broken.md").write_text("---\nvalue: [unterminated\n---\n")
    (graph / "untyped.md").write_text("# A file without frontmatter\n")
    report = validate()
    assert any("broken.md" in error for error in report.errors)
    assert any("untyped.md" in error for error in report.errors)


@pytest.mark.parametrize(
    "atom_id", ["../outside", "/tmp/outside", "knowledge/../../outside", "bad.md", "bad\\path"]
)
def test_path_traversal_rejected(graph, atom_id):
    with pytest.raises(ValueError):
        loader.load(atom_id)


def test_symlink_cannot_escape_graph(graph, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text((graph / "standard-loan-period.md").read_text())
    (graph / "escape.md").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        loader.load("escape")
    assert any("escape.md" in error for error in validate().errors)


def test_challenge_creation_deliberation_rejection_and_backpointer(graph):
    challenges.create_challenge(
        id="revisit-period",
        challenges=["standard-loan-period"],
        basis="disagreement",
        raised_by="Demo Coordinator",
        success_criteria=["Record decision"],
    )
    assert "**Open challenge:** `revisit-period`" in loader.load("standard-loan-period").body
    challenges.append_deliberation(
        "revisit-period", by="Demo Librarian", contribution="Retain period"
    )
    challenges.resolve_challenge(
        "revisit-period", by="Demo Librarian", resolution="rejected", note="Retained"
    )
    unit = loader.load("standard-loan-period")
    assert unit.lifecycle.value == "entitled"
    assert unit.reaffirmed
    assert "**Open challenge:** `revisit-period`" not in unit.body
    assert challenges.load_challenge("revisit-period").status.value == "resolved-rejected"
    with pytest.raises(ValueError):
        challenges.append_deliberation(
            "revisit-period", by="Demo Librarian", contribution="Late edit"
        )
    assert validate().errors == []


def test_challenge_replacement_is_a_candidate_with_no_inherited_approvals(graph):
    challenges.append_deliberation(
        "reminder-timing",
        by="Demo Librarian",
        contribution="Try a different interval",
        proposed_superseding_commitment={
            "id": "revised-reminder",
            "commitment_type": "POLICY",
            "subject": "Revised reminder interval",
            "value": {"days": 1},
            "requires_approval_from": ["Demo Librarian"],
            "approvals": [{"by": "Demo Librarian"}],
        },
    )
    challenges.resolve_challenge("reminder-timing", by="Demo Librarian", resolution="accepted")
    new = loader.load("revised-reminder")
    old = loader.load("return-reminder")
    assert new.lifecycle.value == "candidate" and new.approvals == []
    assert new.supersedes == old.id and old.superseded_by == new.id
    assert old.lifecycle.value == "superseded"
    assert validate().errors == []


def test_challenge_withdrawal_identity_and_retirement(graph):
    with pytest.raises(PermissionError):
        challenges.resolve_challenge("reminder-timing", by="Demo Librarian", resolution="withdrawn")
    challenges.resolve_challenge("reminder-timing", by="Demo Coordinator", resolution="withdrawn")
    assert loader.load("return-reminder").lifecycle.value == "candidate"
    challenges.create_challenge(
        id="retire-reminder",
        challenges=["return-reminder"],
        basis="disagreement",
        raised_by="Demo Coordinator",
        success_criteria=[],
    )
    challenges.resolve_challenge("retire-reminder", by="Demo Librarian", resolution="accepted")
    assert loader.load("return-reminder").lifecycle.value == "superseded"


def test_index_idempotence_and_candidate_separation(graph):
    regenerate()
    assert regenerate(check=True) == []
    assert "return-reminder" not in (graph / "index.md").read_text()
    assert "return-reminder" in (graph / "index-candidates.md").read_text()
    approve()
    assert regenerate(check=True)
    regenerate()
    assert "return-reminder" in (graph / "index.md").read_text()


def test_ripple_and_hash(graph):
    ripples = find_ripples("standard-loan-period", ["14 days"])
    assert any(
        r.atom_id == "standard-loan-period" and r.reason == "value_body_mismatch" for r in ripples
    )
    assert any(r.atom_id == "return-reminder" and r.reason == "reference" for r in ripples)
    unit = loader.load("standard-loan-period")
    assert commitment_content_hash(unit) == commitment_content_hash(replace(unit, approvals=[]))
    assert commitment_content_hash(unit) != commitment_content_hash(
        replace(unit, value={"days": 30})
    )


def test_cli_uses_explicit_root_from_unrelated_directory(graph, tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).parents[1]))
    result = subprocess.run(
        [sys.executable, "-m", "knowledge_graph", "validate"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["records"] == 10
