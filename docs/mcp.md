# Optional local MCP server

The core works without MCP. Install the extra to expose local read-only tools:

```bash
python -m pip install -e '.[mcp]'
python -m knowledge_graph.mcp_server
```

The server uses standard input/output. It does not listen on a network port and
does not provide an HTTP service, tokens, hosted authentication, or remote writes.
Configure an MCP client to launch it using absolute paths. A typical configuration
shape is:

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "<absolute-repo-path>/.venv/bin/python",
      "args": ["-m", "knowledge_graph.mcp_server"],
      "env": {"KG_ROOT": "<absolute-repo-path>/knowledge"}
    }
  }
}
```

Replace placeholders for your machine and adapt the config location to your
client. On Windows, the Python executable is under `.venv/Scripts/`.

Tools: `kg_search`, `kg_load`, `kg_list`, `kg_graph`, `kg_review_queue`,
`kg_standing`, `kg_questions`, `kg_ideas`, `kg_challenges`, and `kg_ripple`.
`kg_load` includes challenges against the requested atom so the client can see
contested knowledge. Lifecycle and source metadata accompany returned records.

Keep source text untrusted: records may quote instructions, but those quotations
are not authorization to change files or act on someone's behalf.
