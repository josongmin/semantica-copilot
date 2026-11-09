# Semantica Copilot

A Python code understanding agent built with LangGraph and the Semantica
Codegraph HTTP API. It turns a question into an execution plan, retrieves code
context, and generates an answer from the collected results.

## Architecture and status

The current [agent graph](src/semantica_copilot/agent/graph.py) is a sequential
pipeline:

```text
intent_router -> plan_executor -> answer_generator -> END
```

It uses a Pydantic state model and a
[Codegraph client](src/semantica_copilot/tools/codegraph.py). Search capabilities
come from the configured Codegraph backend. The graph has no iterative retrieval
loop; the command-line entry point described below is a simpler single-search
integration path.

This is an earlier code understanding implementation. Repository tests and
historical phase documents do not establish current production qualification.

## Local development

Requires Python 3.10 or later, a running
[Semantica Codegraph](https://github.com/josongmin/semantica-codegraph) HTTP API,
and an indexed repository in that backend.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

# Single-search CLI: query followed by comma-separated repository IDs.
# The CLI uses http://localhost:8000 for the Codegraph API.
semantica-copilot "HybridRetriever" semantica-codegraph
```

The module entry point is equivalent:

```sh
python -m semantica_copilot.cli.main "HybridRetriever" semantica-codegraph
```

The LangGraph pipeline and FastAPI application live separately in
[src/semantica_copilot/agent](src/semantica_copilot/agent) and
[src/semantica_copilot/apps/server](src/semantica_copilot/apps/server).
LLM-backed execution also requires provider configuration; see
[src/semantica_copilot/llm/provider.py](src/semantica_copilot/llm/provider.py).

## Tests and design notes

- [tests](tests): agent, client, error handling, and integration tests.
- [docs/adr](docs/adr): intent routing, planning, tool selection, execution, and backend contracts.
- [docs/codegraph-api-adapter.md](docs/codegraph-api-adapter.md): Codegraph API adapter.
- [docs/integration-testing.md](docs/integration-testing.md): integration setup and checks.

Run tests with `python -m pytest` in a configured development environment.
External API and provider tests require their respective services. No test or
benchmark results are claimed by this documentation update.
