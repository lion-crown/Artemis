# Contributing to Artemis

This guide describes how to develop and maintain Artemis locally. Repository hosting, release destinations, and collaboration rules are chosen by the project maintainer.

## Development setup

Prerequisites: Python 3.12+, Node.js 18+, and [uv](https://docs.astral.sh/uv/).

Clone the Artemis repository you have access to, then run:

```bash
make install
make install-hooks
make all
```

For frontend work:

```bash
make dev-frontend
make check-all
```

## Quality requirements

- Keep changes focused and add tests for behavior changes.
- Run `make all` before sharing a change.
- Run `make build-frontend` after dashboard changes; never edit `src/artemis/dashboard/` directly.
- Support Linux and Windows in tests. Prefer `pathlib` and `tmp_path` over platform-specific paths.
- Follow module boundaries and project conventions in [AGENTS.md](AGENTS.md).

## Collaboration and releases

Use the branching, review, release, and repository-hosting workflow selected for Artemis. Do not publish packages, create tags, or push changes without maintainer approval.
