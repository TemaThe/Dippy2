# Changelog

## 0.2.7-fork

- **Subprocess command extraction** — `subprocess.run(["kubectl", "exec", ...])` in Python scripts is now analyzed against config rules and CLI handlers instead of blindly flagging `.run()` as dangerous. Requires `allow-python-module subprocess`. Supports list and string forms, aliases, and all subprocess methods (run, call, check_call, check_output, Popen).
- **`yaml` added to safe Python modules** — PyYAML imports no longer flagged as unknown.
- **`eval` deny rule** — added to example config with instructive message.
- **`/bin/cat` absolute path** — added to example config (Dippy matches `cat` but not `/bin/cat`).
- **`python -c` recommendation** — README now suggests `jq` for JSON parsing in shell scripts.
- **`rm` in tmp folders** — added to example config for AI scratch file cleanup.

## 0.2.6-fork

- Added `yaml` to safe Python modules.

## 0.2.5-fork

- Script unfolding — analyze `bash script.sh` contents line by line.
- Dangerous module explanations — explain why Python modules are flagged.
- `allow-python-module` directive — per-module override for import checks.
- Test coverage: 11,310 tests, 95% statement coverage.
