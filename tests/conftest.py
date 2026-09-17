from pathlib import Path
import shutil

import pytest

from knowledge_graph import config, loader, entitle, challenges, questions, ideas, standing


@pytest.fixture
def graph(tmp_path, monkeypatch):
    """Every mutation uses a copy of the fictional graph, never the shipped files."""
    root = tmp_path / "knowledge"
    shutil.copytree(Path(__file__).parents[1] / "knowledge", root)
    for module in (config, loader, entitle, challenges):
        monkeypatch.setattr(module, "KNOWLEDGE_ROOT", root)
    for module, name in (
        (questions, "QUESTIONS_ROOT"),
        (ideas, "IDEAS_ROOT"),
        (standing, "STANDING_ROOT"),
        (challenges, "CHALLENGES_ROOT"),
    ):
        monkeypatch.setattr(module, name, root / name.removesuffix("_ROOT").lower())
    monkeypatch.setenv("KG_ROOT", str(root))
    return root
