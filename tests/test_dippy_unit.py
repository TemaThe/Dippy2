"""Unit tests for src/dippy/dippy.py covering untested branches."""

from __future__ import annotations

import importlib
import io
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_dippy(monkeypatch):
    """Reset dippy module to Claude mode after each test."""
    yield
    monkeypatch.setattr("sys.argv", ["dippy"])
    monkeypatch.delenv("DIPPY_GEMINI", raising=False)
    monkeypatch.delenv("DIPPY_CURSOR", raising=False)
    monkeypatch.delenv("DIPPY_CLAUDE", raising=False)
    import dippy.dippy

    importlib.reload(dippy.dippy)


# =====================================================================
# TestDetectMode - unknown tool_name branch (line 68-69)
# =====================================================================


class TestDetectMode:
    def test_unknown_tool_name_defaults_to_claude(self):
        from dippy.dippy import _detect_mode_from_input

        result = _detect_mode_from_input({"tool_name": "SomeUnknownTool", "tool_input": {}})
        assert result == "claude"

    def test_unknown_tool_name_logs_warning(self, caplog):
        from dippy.dippy import _detect_mode_from_input

        with caplog.at_level(logging.WARNING):
            _detect_mode_from_input({"tool_name": "WeirdTool", "tool_input": {}})
        assert "Unknown tool_name" in caplog.text
        assert "WeirdTool" in caplog.text

    def test_mcp_tool_name_no_warning(self, caplog):
        from dippy.dippy import _detect_mode_from_input

        with caplog.at_level(logging.WARNING):
            result = _detect_mode_from_input({"tool_name": "mcp__github__issue", "tool_input": {}})
        assert result == "claude"
        assert "Unknown tool_name" not in caplog.text

    def test_empty_tool_name_no_warning(self, caplog):
        from dippy.dippy import _detect_mode_from_input

        with caplog.at_level(logging.WARNING):
            result = _detect_mode_from_input({"tool_name": "", "tool_input": {}})
        assert result == "claude"
        assert "Unknown tool_name" not in caplog.text


# =====================================================================
# TestGetLogFile - gemini/cursor log paths (lines 82-85)
# =====================================================================


class TestGetLogFile:
    def test_claude_log_path(self, monkeypatch):
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        path = dippy.dippy._get_log_file()
        assert path == Path.home() / ".claude" / "hook-approvals.log"

    def test_gemini_log_path(self, monkeypatch):
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "MODE", "gemini")
        path = dippy.dippy._get_log_file()
        assert path == Path.home() / ".gemini" / "hook-approvals.log"

    def test_cursor_log_path(self, monkeypatch):
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "MODE", "cursor")
        path = dippy.dippy._get_log_file()
        assert path == Path.home() / ".cursor" / "hook-approvals.log"


# =====================================================================
# TestSetupLogging - OSError catch (lines 100-101)
# =====================================================================


class TestSetupLogging:
    def test_setup_logging_success(self, tmp_path, monkeypatch):
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_get_log_file", lambda: tmp_path / "test.log")
        # Should not raise
        dippy.dippy.setup_logging()

    def test_setup_logging_oserror_silent(self, monkeypatch):
        import dippy.dippy

        def _raise_oserror():
            raise OSError("disk full")

        monkeypatch.setattr(dippy.dippy, "_get_log_file", _raise_oserror)
        # Should not raise - silently ignores OSError
        dippy.dippy.setup_logging()


# =====================================================================
# TestDenyFormats - gemini/cursor deny output (lines 158-169)
# =====================================================================


class TestDenyFormats:
    def test_deny_gemini_format(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["dippy", "--gemini"])
        import dippy.dippy

        importlib.reload(dippy.dippy)

        result = dippy.dippy.deny("blocked by rule")
        assert result["decision"] == "deny"
        assert "blocked by rule" in result["reason"]
        assert "hookSpecificOutput" not in result

    def test_deny_cursor_format(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["dippy", "--cursor"])
        import dippy.dippy

        importlib.reload(dippy.dippy)

        result = dippy.dippy.deny("blocked by rule")
        assert result["permission"] == "deny"
        assert "blocked by rule" in result["user_message"]
        assert "blocked by rule" in result["userMessage"]
        assert "hookSpecificOutput" not in result

    def test_deny_claude_format(self):
        import dippy.dippy

        # Default mode is claude
        result = dippy.dippy.deny("blocked")
        hso = result["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert "blocked" in hso["permissionDecisionReason"]


# =====================================================================
# TestCheckMcpTool - ask decision path (line 245)
# =====================================================================


class TestCheckMcpTool:
    def test_mcp_tool_ask_decision(self):
        from dippy.core.config import Config, Rule
        from dippy.dippy import check_mcp_tool

        config = Config(mcp_rules=[Rule(decision="ask", pattern="mcp__*", message="needs review")])
        result = check_mcp_tool("mcp__github__create_pr", config)
        hso = result.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "ask"
        assert "needs review" in hso.get("permissionDecisionReason", "")

    def test_mcp_tool_no_match_returns_empty(self):
        from dippy.core.config import Config
        from dippy.dippy import check_mcp_tool

        config = Config()  # No MCP rules
        result = check_mcp_tool("mcp__github__get_issue", config)
        assert result == {}

    def test_mcp_tool_allow_decision(self):
        from dippy.core.config import Config, Rule
        from dippy.dippy import check_mcp_tool

        config = Config(mcp_rules=[Rule(decision="allow", pattern="mcp__github__*")])
        result = check_mcp_tool("mcp__github__get_issue", config)
        hso = result.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow"

    def test_mcp_tool_deny_decision(self):
        from dippy.core.config import Config, Rule
        from dippy.dippy import check_mcp_tool

        config = Config(mcp_rules=[Rule(decision="deny", pattern="mcp__dangerous__*")])
        result = check_mcp_tool("mcp__dangerous__delete_all", config)
        hso = result.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "deny"


# =====================================================================
# TestHandleMcpPostToolUse - message output (lines 250-252)
# =====================================================================


class TestHandleMcpPostToolUse:
    def test_mcp_post_tool_prints_message(self, capsys):
        from dippy.core.config import Config, Rule
        from dippy.dippy import handle_mcp_post_tool_use

        config = Config(after_mcp_rules=[Rule(decision="allow", pattern="mcp__gh__*", message="PR created!")])
        handle_mcp_post_tool_use("mcp__gh__create_pr", config)
        captured = capsys.readouterr()
        assert "PR created!" in captured.out

    def test_mcp_post_tool_no_match_silent(self, capsys):
        from dippy.core.config import Config
        from dippy.dippy import handle_mcp_post_tool_use

        config = Config()  # No after_mcp rules
        handle_mcp_post_tool_use("mcp__gh__create_pr", config)
        captured = capsys.readouterr()
        assert captured.out == ""


# =====================================================================
# TestMain - main() function branches (lines 270-371)
# =====================================================================


def _make_stdin(data: dict) -> io.StringIO:
    """Create a StringIO with JSON data for sys.stdin."""
    return io.StringIO(json.dumps(data))


class TestMain:
    def test_auto_detect_mode_from_input(self, monkeypatch, capsys):
        """Line 281-283: auto-detect mode when no explicit flag."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", None)
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({"tool_name": "shell", "tool_input": {"command": "echo hi"}}),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        # Gemini auto-detected, so output is gemini format
        assert "decision" in output
        assert output["decision"] == "allow"

    def test_cwd_from_tool_input(self, monkeypatch, capsys, tmp_path):
        """Lines 289-293: cwd extracted from tool_input."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "Bash",
                "tool_input": {"command": "echo hi", "cwd": str(tmp_path)},
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_config_error_returns_ask(self, monkeypatch, capsys):
        """Lines 301-304: ConfigError triggers ask response."""
        import dippy.dippy
        from dippy.core.config import ConfigError

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({"tool_name": "Bash", "tool_input": {"command": "ls"}}),
        )
        monkeypatch.setattr(
            "dippy.dippy.load_config",
            lambda cwd: (_ for _ in ()).throw(ConfigError("bad config")),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        hso = output["hookSpecificOutput"]
        assert hso["permissionDecision"] == "ask"
        assert "config error" in hso["permissionDecisionReason"]

    def test_cursor_mode_command_extraction(self, monkeypatch, capsys):
        """Lines 312-315: Cursor mode extracts command from top-level."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "cursor")
        monkeypatch.setattr(dippy.dippy, "MODE", "cursor")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({"command": "echo hello", "cwd": "/tmp"}),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["permission"] == "allow"

    def test_mcp_bypass_permissions(self, monkeypatch, capsys):
        """Lines 323-330: MCP tool with bypassPermissions mode."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "mcp__github__get_issue",
                "tool_input": {},
                "permission_mode": "bypassPermissions",
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "bypassPermissions" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_mcp_post_tool_use(self, monkeypatch, capsys):
        """Lines 332-334: MCP PostToolUse event."""
        import dippy.dippy
        from dippy.core.config import Config, Rule

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        mock_config = Config(after_mcp_rules=[Rule(decision="allow", pattern="mcp__gh__*", message="done!")])
        monkeypatch.setattr("dippy.dippy.load_config", lambda cwd: mock_config)
        monkeypatch.setattr("dippy.dippy.configure_logging", lambda cfg: None)
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "mcp__gh__create_pr",
                "tool_input": {},
                "hook_event_name": "PostToolUse",
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        assert "done!" in captured.out

    def test_mcp_pre_tool_use_check(self, monkeypatch, capsys):
        """Lines 336-338: MCP PreToolUse check."""
        import dippy.dippy
        from dippy.core.config import Config, Rule

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        mock_config = Config(mcp_rules=[Rule(decision="allow", pattern="mcp__safe__*")])
        monkeypatch.setattr("dippy.dippy.load_config", lambda cwd: mock_config)
        monkeypatch.setattr("dippy.dippy.configure_logging", lambda cfg: None)
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "mcp__safe__read",
                "tool_input": {},
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_non_shell_tool_passthrough(self, monkeypatch, capsys):
        """Lines 342-344: Non-shell, non-MCP tool returns empty dict."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({"tool_name": "Read", "tool_input": {"path": "/tmp/x"}}),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output == {}

    def test_bypass_permissions_shell(self, monkeypatch, capsys):
        """Lines 349-355: Shell command with bypassPermissions."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /"},
                "permission_mode": "bypassPermissions",
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_post_tool_use_shell(self, monkeypatch, capsys):
        """Lines 358-360: PostToolUse for shell commands."""
        import dippy.dippy
        from dippy.core.config import Config, Rule

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        mock_config = Config(after_rules=[Rule(decision="allow", pattern="git push*", message="pushed!")])
        monkeypatch.setattr("dippy.dippy.load_config", lambda cwd: mock_config)
        monkeypatch.setattr("dippy.dippy.configure_logging", lambda cfg: None)
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "Bash",
                "tool_input": {"command": "git push origin main"},
                "hook_event_name": "PostToolUse",
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        assert "pushed!" in captured.out

    def test_json_decode_error(self, monkeypatch, capsys):
        """Lines 366-368: Invalid JSON input."""
        import dippy.dippy

        monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output == {}

    def test_generic_exception(self, monkeypatch, capsys):
        """Lines 369-371: Generic exception handling."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")

        def _exploding_stdin_load(fp):
            raise RuntimeError("something broke")

        monkeypatch.setattr("json.load", _exploding_stdin_load)
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output == {}

    def test_default_cwd_when_none_in_input(self, monkeypatch, capsys):
        """Lines 294-295: Default cwd to Path.cwd() when not in input."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "Bash",
                "tool_input": {"command": "echo hi"},
                # No cwd anywhere
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_mcp_dont_ask_bypass(self, monkeypatch, capsys):
        """Lines 326-330: MCP tool with dontAsk permission mode."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "mcp__github__get_issue",
                "tool_input": {},
                "permission_mode": "dontAsk",
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "dontAsk" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_top_level_cwd(self, monkeypatch, capsys, tmp_path):
        """Lines 288-293: cwd extracted from top-level input field."""
        import dippy.dippy

        monkeypatch.setattr(dippy.dippy, "_EXPLICIT_MODE", "claude")
        monkeypatch.setattr(dippy.dippy, "MODE", "claude")
        monkeypatch.setattr(
            "sys.stdin",
            _make_stdin({
                "tool_name": "Bash",
                "tool_input": {"command": "echo hi"},
                "cwd": str(tmp_path),
            }),
        )
        dippy.dippy.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
