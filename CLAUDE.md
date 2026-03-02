# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First Steps (for Claude Code)
1. Read this file completely
2. Use Serena (LSP) as your PRIMARY tool for code navigation and editing
3. Never read raw source files before trying Serena's symbolic tools first

## Code Research Tools

**Never read full source files before trying Serena first!**
NEVER use standard terminal grep/cat/head for Python source files.
Rely on the symbol data provided by Serena to save context tokens.

### Serena (MCP: serena) — Semantic Code Analysis via LSP

Serena provides IDE-like semantic code tools powered by Language Server Protocol (Pyright for Python).
Use Serena for ALL code navigation, exploration, and editing — it understands code structure, references, and types.

**Key tools (read-only research):**

| Tool                                  | Purpose                                        | When to use                                |
| ------------------------------------- | ---------------------------------------------- | ------------------------------------------ |
| `jet_brains_find_symbol`              | Search for function/class/variable by name     | "Where is `_analyze_command` defined?"     |
| `jet_brains_find_referencing_symbols` | Find all symbols that reference a given symbol | "Who calls `analyze()`?"                   |
| `jet_brains_get_symbols_overview`     | List all top-level symbols in a file           | "What functions are in analyzer.py?"       |
| `jet_brains_type_hierarchy`           | Get type hierarchy (supertypes/subtypes)       | "What classes inherit from `BaseHandler`?" |

**Key tools (editing):**

| Tool            | Purpose                | When to use                             |
| --------------- | ---------------------- | --------------------------------------- |
| `rename_symbol` | Rename across codebase | Renaming a variable/function everywhere |



### NEVER use following Serena MCP commands:
`search_for_pattern`
`list_dir`
`find_file`
`replace_content`

**Serena workflow:**
1. `jet_brains_get_symbols_overview` on the target file → understand file structure
2. `jet_brains_find_symbol("classify", depth=1)` → find exact definition with signature
3. `jet_brains_find_referencing_symbols` → find all callers
4. Do NOT request `include_body=True` unless you need the implementation — be frugal with context
5. Use `replace_symbol_body` or `replace_content` for edits — never raw file writes for code changes

**Context efficiency rules:**
- Default to `include_body=False` when exploring — read signatures first, bodies only when needed
- Use `jet_brains_get_symbols_overview` before diving into a file — avoid reading entire files
- Prefer `jet_brains_find_symbol` with `depth=1` first, increase only if needed
- When tracing call chains, collect symbol names first, then read bodies selectively

## Project Overview

Dippy is a shell command hook that auto-approves safe commands for Claude Code, Gemini CLI, and Cursor while blocking destructive ones. Zero production dependencies — uses a vendored hand-written bash parser ([Parable](https://github.com/ldayton/Parable)). This is a fork of [ldayton/Dippy](https://github.com/ldayton/Dippy).

Configuration docs: [Dippy Wiki](https://github.com/ldayton/Dippy/wiki)

## Commands

Build tool is [just](https://github.com/casey/just). Package manager is [uv](https://github.com/astral-sh/uv).

```bash
just test                     # Run tests on Python 3.14 (default)
just test -- tests/cli/test_git.py  # Run a specific test file
just test -- -k "test_name"   # Run tests matching a pattern
just test-all                 # Parallel tests on Python 3.8–3.14
just lint                     # Ruff linter (--fix to auto-fix)
just fmt                      # Ruff formatter (--fix to apply)
just check                    # All checks in parallel (tests, lint, fmt, lock, style, parable)
just check-parable            # Verify vendored Parable checksum
just update-parable           # Update Parable from upstream
```

## Architecture

### Hook Flow

```
stdin (JSON) → main() in dippy.py
  → detect mode (claude/gemini/cursor)
  → load config (~/.dippy/config + .dippy)
  → route by event type:
      PreToolUse  → check_command() → analyze() → Decision(allow|ask|deny)
      PostToolUse → match_after rules → feedback message
  → output JSON response (format varies by mode)
```

### Key Modules

- **`src/dippy/dippy.py`** — Entry point. Mode detection, config loading, response formatting.
- **`src/dippy/core/analyzer.py`** — Single-pass recursive AST walk. Parses command via Parable, then analyzes each node (commands, pipelines, redirects, substitutions). Most restrictive child decision wins (deny > ask > allow).
- **`src/dippy/core/config.py`** — Config parsing, rule matching (fnmatch glob), logging. Loads global + project + env configs.
- **`src/dippy/core/script_unfold.py`** — Fork feature. When command is `bash script.sh`, reads and analyzes the script's contents line by line.
- **`src/dippy/cli/`** — 88 CLI-specific handlers (git, docker, kubectl, aws, etc.). Auto-discovered at import. Each exports `COMMANDS` list and `classify(ctx) → Classification(allow|ask|delegate)`.
- **`src/dippy/vendor/parable.py`** — Vendored bash parser (~10K lines). Do not edit directly; update via `just update-parable`.

### Handler Interface

Each handler in `src/dippy/cli/` implements:
```python
COMMANDS = ["git"]  # command names this handler matches

def classify(ctx: HandlerContext) -> Classification:
    # return Classification("allow"|"ask"|"delegate", ...)
```

`delegate` means "unwrap the inner command and re-analyze" (e.g., `bash -c "..."`, `docker exec ... cmd`).

### Decision Priority

1. Config rules (highest) — user's allow/deny/deny-redirect rules
2. CLI handler — handler-specific classification
3. Wrapper unwrap — `timeout`, `time`, `command` skip to inner command
4. Script unfolding — analyze script contents
5. Allowlists — known safe read-only commands
6. Default → `ask`

### Test Fixtures (conftest.py)

- `check(command, config?, cwd?)` — Returns full hook response dict. Assert with `is_approved(result)` or `needs_confirmation(result)`.
- `check_single(command, config?, cwd?)` — Returns `(decision, reason)` tuple via `analyze()` directly.
- `hook_input(command)` — Generates stdin JSON for integration tests.
