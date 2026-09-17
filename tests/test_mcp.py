import asyncio
import json
import os
from pathlib import Path
import sys

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_protocol_and_read_tools(graph):
    async def exercise():
        env = {**os.environ, "KG_ROOT": str(graph), "PYTHONPATH": str(Path(__file__).parents[1])}
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "knowledge_graph.mcp_server"], env=env
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {t.name for t in tools.tools} == {
                    "kg_search",
                    "kg_load",
                    "kg_list",
                    "kg_graph",
                    "kg_review_queue",
                    "kg_standing",
                    "kg_questions",
                    "kg_ideas",
                    "kg_challenges",
                    "kg_ripple",
                }
                result = await session.call_tool("kg_load", {"atom_id": "return-reminder"})
                assert not result.isError
                data = json.loads(result.content[0].text)
                assert data["unit"]["lifecycle"] == "candidate"
                assert data["challenges"][0]["id"] == "reminder-timing"
                result = await session.call_tool("kg_search", {"query": "loan period"})
                assert "standard-loan-period" in result.content[0].text
                result = await session.call_tool("kg_load", {"atom_id": "../outside"})
                assert result.isError

    asyncio.run(exercise())
