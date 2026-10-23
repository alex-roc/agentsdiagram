# 6. Diagrams in CI and docs

Two things to automate: catching agent mistakes before they ship, and keeping the diagram in
your README up to date.

## `check` in CI

`agentsdiagram check` exits with 1 on errors, so it can gate a pull request. It reads code only,
so the job needs no API keys and none of your dependencies.

```yaml
# .github/workflows/agents.yml
name: Agents
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10.3.2
      - run: uvx agentsdiagram check . --strict
```

`--strict` also fails on warnings (for example a smolagents `@tool` without type hints, or
PydanticAI v1 API). Use `--json` to feed the diagnostics to other tools.

## pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: agentsdiagram
        name: agentsdiagram check
        entry: uvx agentsdiagram check
        language: system
        pass_filenames: false
        types: [python]
```

## A diagram in your README

GitHub renders Mermaid. Generate a Markdown file with the diagram and link it, or paste the block
into your README:

```bash
uvx agentsdiagram scan . -f markdown -o docs/AGENTS.md --title "Our agents"
```

To keep it fresh, regenerate it in CI and fail if it changed:

```yaml
      - run: uvx agentsdiagram scan . -f markdown -o docs/AGENTS.md --title "Our agents"
      - run: git diff --exit-code docs/AGENTS.md
```

For an interactive version, publish the HTML page (`-f html`) with GitHub Pages, as this project
does for its [live demos](https://alex-roc.github.io/agentsdiagram/).

## Big repositories

- Restrict the analysis in `pyproject.toml`:

  ```toml
  [tool.agentsdiagram]
  include = ["src/**"]
  exclude = ["tests/**", "notebooks/**"]
  ```

- Files that do not mention a framework are skipped before parsing, and the rest are parsed once,
  so a 200-file project takes a few seconds.
- If Mermaid complains about the size, use `-f html`, which has no limit.

## Next

[7. With coding agents](07-coding-agents.md).
