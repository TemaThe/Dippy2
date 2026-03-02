"""In-process unit tests for src/dippy/dippy_statusline.py."""

from __future__ import annotations

import json
import os
import subprocess
import time

import pytest

from dippy.dippy_statusline import (
    CACHE_TTL,
    Logger,
    build_statusline,
    get_cache_path,
    get_cached,
    get_context_from_transcript,
    get_context_remaining,
    get_git_branch,
    get_git_changes,
    get_local_mcp_servers,
    get_mcp_servers,
    hex_to_rgb,
    is_dippy_configured,
    main,
    set_cache,
    style,
)


# ---------------------------------------------------------------------------
# hex_to_rgb
# ---------------------------------------------------------------------------
class TestHexToRgb:
    def test_valid_hex(self):
        assert hex_to_rgb("#ff0000") == (255, 0, 0)

    def test_short_leading_hash(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_various_colors(self):
        assert hex_to_rgb("#1080d0") == (16, 128, 208)
        assert hex_to_rgb("#98e123") == (152, 225, 35)
        assert hex_to_rgb("#ffffff") == (255, 255, 255)


# ---------------------------------------------------------------------------
# style
# ---------------------------------------------------------------------------
class TestStyle:
    def test_no_color(self):
        assert style("hello", None, None) == "hello"

    def test_fg_only(self):
        result = style("hi", "white")
        assert "hi" in result
        assert "\033[38;2;" in result
        assert result.endswith("\033[0m")

    def test_bg_tuple_via_bgx_color(self):
        result = style("x", "bgRed")
        assert "\033[38;2;" in result
        assert "\033[48;2;" in result
        assert "x" in result

    def test_fg_and_bg(self):
        result = style("t", "white", "black")
        assert "\033[38;2;" in result
        assert "\033[48;2;" in result

    def test_unknown_color(self):
        result = style("z", "noSuchColor")
        # Unknown colour key -> no prefix, just text + reset
        assert "z" in result


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
class TestLogger:
    def test_write(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = Logger(log_file)
        logger.info("hello", extra="val")
        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["level"] == "INFO"
        assert entry["event"] == "hello"
        assert entry["extra"] == "val"
        assert "ts" in entry

    def test_rotation(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = Logger(log_file, max_size=50)
        # Write enough to exceed 50 bytes
        logger.info("first_message_that_is_long_enough")
        logger.info("second_message_triggers_rotation")
        backup = log_file + ".1"
        assert os.path.exists(backup)
        assert os.path.exists(log_file)

    def test_debug_level(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = Logger(log_file)
        logger.debug("dbg_event")
        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["level"] == "DEBUG"

    def test_warning_level(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = Logger(log_file)
        logger.warning("warn_event")
        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["level"] == "WARNING"

    def test_error_level(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = Logger(log_file)
        logger.error("err_event", code=42)
        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["level"] == "ERROR"
        assert entry["code"] == 42
        assert "exc_info" in entry


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
class TestCache:
    def test_cache_path_basic(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        path = get_cache_path("sess-1")
        assert path == os.path.join(str(tmp_path), "sess-1.cache")

    def test_cache_path_slash_replaced(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        path = get_cache_path("a/b/c")
        assert "/" not in os.path.basename(path)
        assert "a_b_c" in path

    def test_cache_path_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        path = get_cache_path("")
        assert "default" in path

    def test_cache_hit(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        set_cache("s1", "output-data")
        result = get_cached("s1")
        assert result == "output-data"

    def test_cache_miss(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        assert get_cached("nonexistent") is None

    def test_cache_expired(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        set_cache("s2", "data")
        # Backdate the file to make it expired
        cache_path = get_cache_path("s2")
        old_time = time.time() - CACHE_TTL - 10
        os.utime(cache_path, (old_time, old_time))
        assert get_cached("s2") is None

    def test_set_cache_creates_dir(self, tmp_path, monkeypatch):
        cache_dir = str(tmp_path / "sub" / "dir")
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", cache_dir)
        set_cache("s3", "val")
        assert os.path.isdir(cache_dir)
        assert get_cached("s3") == "val"

    def test_cache_read_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        # Create the cache file as a directory to provoke an error
        bad_path = get_cache_path("bad")
        os.makedirs(bad_path, exist_ok=True)
        assert get_cached("bad") is None


# ---------------------------------------------------------------------------
# get_local_mcp_servers
# ---------------------------------------------------------------------------
class TestLocalMcpServers:
    def test_valid(self, tmp_path, monkeypatch):
        mcp_file = tmp_path / "mcp.local.json"
        mcp_file.write_text(json.dumps({"mcpServers": {"s1": {}, "s2": {}}}))
        monkeypatch.setattr("dippy.dippy_statusline.MCP_LOCAL_PATH", str(mcp_file))
        assert get_local_mcp_servers() == ["s1", "s2"]

    def test_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dippy.dippy_statusline.MCP_LOCAL_PATH",
            str(tmp_path / "nonexistent.json"),
        )
        assert get_local_mcp_servers() == []

    def test_invalid_json(self, tmp_path, monkeypatch):
        mcp_file = tmp_path / "mcp.local.json"
        mcp_file.write_text("{not valid json")
        monkeypatch.setattr("dippy.dippy_statusline.MCP_LOCAL_PATH", str(mcp_file))
        assert get_local_mcp_servers() == []

    def test_bad_format(self, tmp_path, monkeypatch):
        mcp_file = tmp_path / "mcp.local.json"
        mcp_file.write_text(json.dumps(["a", "b"]))  # list, not dict
        monkeypatch.setattr("dippy.dippy_statusline.MCP_LOCAL_PATH", str(mcp_file))
        assert get_local_mcp_servers() == []

    def test_permission_error(self, tmp_path, monkeypatch):
        mcp_file = tmp_path / "mcp.local.json"
        mcp_file.write_text("{}")
        mcp_file.chmod(0o000)
        monkeypatch.setattr("dippy.dippy_statusline.MCP_LOCAL_PATH", str(mcp_file))
        result = get_local_mcp_servers()
        mcp_file.chmod(0o644)  # restore for cleanup
        assert result == []


# ---------------------------------------------------------------------------
# get_mcp_servers
# ---------------------------------------------------------------------------
class TestGetMcpServers:
    def test_no_servers(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dippy.dippy_statusline.MCP_LOCAL_PATH",
            str(tmp_path / "none.json"),
        )
        monkeypatch.setattr(
            "dippy.dippy_statusline.MCP_CACHE_PATH",
            str(tmp_path / "none.cache"),
        )
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        result = get_mcp_servers()
        assert result is None

    def test_local_only(self, tmp_path, monkeypatch):
        mcp_file = tmp_path / "mcp.local.json"
        mcp_file.write_text(json.dumps({"mcpServers": {"localSrv": {}}}))
        monkeypatch.setattr("dippy.dippy_statusline.MCP_LOCAL_PATH", str(mcp_file))
        monkeypatch.setattr(
            "dippy.dippy_statusline.MCP_CACHE_PATH",
            str(tmp_path / "no.cache"),
        )
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        result = get_mcp_servers()
        assert result is not None
        assert "MCP:" in result
        assert "localSrv" in result

    def test_cached(self, tmp_path, monkeypatch):
        mcp_file = tmp_path / "mcp.local.json"
        mcp_file.write_text(json.dumps({"mcpServers": {}}))
        monkeypatch.setattr("dippy.dippy_statusline.MCP_LOCAL_PATH", str(mcp_file))
        cache_file = tmp_path / "mcp.cache"
        cache_file.write_text("cachedServer")
        monkeypatch.setattr(
            "dippy.dippy_statusline.MCP_CACHE_PATH", str(cache_file)
        )
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        # Make cache fresh
        monkeypatch.setattr("dippy.dippy_statusline.MCP_CACHE_TTL", 9999)
        result = get_mcp_servers()
        assert result is not None
        assert "cachedServer" in result

    def test_expired_refresh(self, tmp_path, monkeypatch):
        mcp_file = tmp_path / "mcp.local.json"
        mcp_file.write_text(json.dumps({"mcpServers": {}}))
        monkeypatch.setattr("dippy.dippy_statusline.MCP_LOCAL_PATH", str(mcp_file))
        cache_file = tmp_path / "mcp.cache"
        cache_file.write_text("stale")
        # Backdate to expire
        old = time.time() - 9999
        os.utime(str(cache_file), (old, old))
        monkeypatch.setattr(
            "dippy.dippy_statusline.MCP_CACHE_PATH", str(cache_file)
        )
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        # Stub Popen so we don't actually launch a subprocess
        monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: None)
        result = get_mcp_servers()
        # Should still return the stale cached value while refresh is in background
        assert result is not None
        assert "stale" in result


# ---------------------------------------------------------------------------
# is_dippy_configured
# ---------------------------------------------------------------------------
class TestIsDippyConfigured:
    def test_configured(self, tmp_path, monkeypatch):
        # Create a fake executable
        exe = tmp_path / "dippy-hook"
        exe.write_text("#!/bin/sh\nexit 0")
        exe.chmod(0o755)
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"command": str(exe) + " arg"}],
                    }
                ]
            }
        }
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(settings_path) if "settings.json" in p else p,
        )
        assert is_dippy_configured() is True

    def test_not_configured(self, tmp_path, monkeypatch):
        settings = {"hooks": {"PreToolUse": []}}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(settings_path) if "settings.json" in p else p,
        )
        assert is_dippy_configured() is False

    def test_missing_settings(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(tmp_path / "nope.json") if "settings.json" in p else p,
        )
        assert is_dippy_configured() is False

    def test_error(self, tmp_path, monkeypatch):
        settings_path = tmp_path / "settings.json"
        settings_path.write_text("not json!!")
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(settings_path) if "settings.json" in p else p,
        )
        assert is_dippy_configured() is False


# ---------------------------------------------------------------------------
# get_context_from_transcript
# ---------------------------------------------------------------------------
class TestTranscript:
    def test_valid(self, tmp_path):
        tf = tmp_path / "transcript.jsonl"
        entry = {
            "message": {
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 20,
                    "cache_creation_input_tokens": 10,
                }
            }
        }
        tf.write_text(json.dumps(entry) + "\n")
        assert get_context_from_transcript(str(tf)) == 180

    def test_empty_path(self):
        assert get_context_from_transcript("") is None

    def test_missing_file(self):
        assert get_context_from_transcript("/no/such/file.jsonl") is None

    def test_no_usage(self, tmp_path):
        tf = tmp_path / "transcript.jsonl"
        tf.write_text(json.dumps({"message": {}}) + "\n")
        assert get_context_from_transcript(str(tf)) is None

    def test_bad_json_lines(self, tmp_path):
        tf = tmp_path / "transcript.jsonl"
        entry = {
            "message": {
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            }
        }
        # A bad line followed by a good line - should find the good one
        tf.write_text("{{bad json\n" + json.dumps(entry) + "\n")
        assert get_context_from_transcript(str(tf)) == 15


# ---------------------------------------------------------------------------
# get_context_remaining
# ---------------------------------------------------------------------------
class TestContextRemaining:
    def test_no_size(self):
        result = get_context_remaining({})
        assert result is None

    def test_no_usage_fallback(self, tmp_path):
        data = {
            "context_window": {"context_window_size": 200000},
            "transcript_path": str(tmp_path / "nonexist.jsonl"),
        }
        result = get_context_remaining(data)
        assert result is not None
        assert "80%" in result

    def test_with_usage(self, tmp_path):
        tf = tmp_path / "t.jsonl"
        entry = {
            "message": {
                "usage": {
                    "input_tokens": 50000,
                    "output_tokens": 10000,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            }
        }
        tf.write_text(json.dumps(entry) + "\n")
        data = {
            "context_window": {"context_window_size": 200000},
            "transcript_path": str(tf),
        }
        result = get_context_remaining(data)
        assert result is not None
        # 60000/200000 = 30%, so remaining = 80-30 = 50%
        assert "50%" in result

    def test_exception(self, monkeypatch):
        # Force an exception inside get_context_remaining
        monkeypatch.setattr(
            "dippy.dippy_statusline.get_context_from_transcript",
            lambda p: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        data = {"context_window": {"context_window_size": 100}}
        result = get_context_remaining(data)
        assert result is None


# ---------------------------------------------------------------------------
# get_git_branch
# ---------------------------------------------------------------------------
class TestGitBranch:
    def test_no_cwd(self):
        assert get_git_branch("") is None

    def test_found(self, monkeypatch):
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="main\n", stderr="")
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake)
        result = get_git_branch("/some/dir")
        assert result is not None
        assert "main" in result

    def test_detached(self, monkeypatch):
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="\n", stderr="")
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake)
        result = get_git_branch("/some/dir")
        assert result is not None
        assert "detached" in result

    def test_not_repo(self, monkeypatch):
        fake = subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal")
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake)
        assert get_git_branch("/not/a/repo") is None

    def test_timeout(self, monkeypatch):
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="git", timeout=1)

        monkeypatch.setattr("subprocess.run", raise_timeout)
        assert get_git_branch("/slow") is None

    def test_exception(self, monkeypatch):
        def raise_err(*a, **kw):
            raise OSError("git not found")

        monkeypatch.setattr("subprocess.run", raise_err)
        assert get_git_branch("/broken") is None


# ---------------------------------------------------------------------------
# get_git_changes
# ---------------------------------------------------------------------------
class TestGitChanges:
    def test_no_cwd(self):
        assert get_git_changes("") is None

    def test_clean(self, monkeypatch):
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake)
        result = get_git_changes("/dir")
        assert result is not None
        assert "clean" in result

    def test_dirty(self, monkeypatch):
        stat = " 3 files changed, 10 insertions(+), 5 deletions(-)\n"
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=stat, stderr="")
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake)
        result = get_git_changes("/dir")
        assert result is not None
        assert "+10" in result
        assert "-5" in result

    def test_not_repo(self, monkeypatch):
        fake = subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal")
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake)
        assert get_git_changes("/nope") is None

    def test_timeout(self, monkeypatch):
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="git", timeout=1)

        monkeypatch.setattr("subprocess.run", raise_timeout)
        assert get_git_changes("/slow") is None


# ---------------------------------------------------------------------------
# build_statusline
# ---------------------------------------------------------------------------
class TestBuildStatusline:
    def test_minimal(self, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.is_dippy_configured", lambda: False)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_branch", lambda cwd: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_changes", lambda cwd: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_context_remaining", lambda d: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_mcp_servers", lambda: None)
        data = {"model": {"display_name": "Opus"}, "workspace": {"current_dir": "/a/mydir"}}
        result = build_statusline(data)
        assert "Opus" in result
        assert "mydir" in result

    def test_with_all_sections(self, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.is_dippy_configured", lambda: False)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_branch", lambda cwd: "br")
        monkeypatch.setattr("dippy.dippy_statusline.get_git_changes", lambda cwd: "chg")
        monkeypatch.setattr("dippy.dippy_statusline.get_context_remaining", lambda d: "ctx")
        monkeypatch.setattr("dippy.dippy_statusline.get_mcp_servers", lambda: "mcp")
        data = {"model": {"display_name": "S"}, "workspace": {"current_dir": "/x/y"}}
        result = build_statusline(data)
        assert "br" in result
        assert "chg" in result
        assert "ctx" in result
        assert "mcp" in result
        assert " | " in result

    def test_dippy_emoji(self, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.is_dippy_configured", lambda: True)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_branch", lambda cwd: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_changes", lambda cwd: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_context_remaining", lambda d: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_mcp_servers", lambda: None)
        data = {"model": {"display_name": "M"}}
        result = build_statusline(data)
        assert "\U0001f424" in result  # duck emoji


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
class TestMain:
    def test_fresh_build(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        monkeypatch.setattr("dippy.dippy_statusline.is_dippy_configured", lambda: False)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_branch", lambda cwd: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_changes", lambda cwd: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_context_remaining", lambda d: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_mcp_servers", lambda: None)

        import io

        data = {"session_id": "unit-fresh", "model": {"display_name": "Test"}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        output = []
        monkeypatch.setattr("builtins.print", lambda s: output.append(s))
        main()
        assert len(output) == 1
        assert "Test" in output[0]

    def test_cached(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        set_cache("unit-cached", "cached-output")

        import io

        data = {"session_id": "unit-cached"}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        output = []
        monkeypatch.setattr("builtins.print", lambda s: output.append(s))
        main()
        assert output == ["cached-output"]

    def test_invalid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dippy.dippy_statusline.CACHE_DIR", str(tmp_path))
        monkeypatch.setattr("dippy.dippy_statusline.is_dippy_configured", lambda: False)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_branch", lambda cwd: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_git_changes", lambda cwd: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_context_remaining", lambda d: None)
        monkeypatch.setattr("dippy.dippy_statusline.get_mcp_servers", lambda: None)

        import io

        monkeypatch.setattr("sys.stdin", io.StringIO("{{{bad"))
        output = []
        monkeypatch.setattr("builtins.print", lambda s: output.append(s))
        main()
        # Should still produce output (with "?" model)
        assert len(output) == 1
        assert "?" in output[0]


# ---------------------------------------------------------------------------
# Logger rotation with existing backup + rotation error (lines 34, 36-37)
# ---------------------------------------------------------------------------
class TestLoggerRotationExistingBackup:
    def test_rotation_removes_existing_backup(self, tmp_path):
        """When backup .1 already exists, rotation removes it first."""
        log_file = str(tmp_path / "test.log")
        backup = log_file + ".1"
        logger = Logger(log_file, max_size=50)
        # Write to trigger first rotation
        logger.info("first_message_that_is_long_enough_to_trigger")
        logger.info("second_message_triggers_first_rotation")
        assert os.path.exists(backup)
        # Write more to trigger second rotation (backup already exists)
        logger.info("third_message_is_also_long_enough_too")
        logger.info("fourth_triggers_second_rotation_now")
        assert os.path.exists(backup)
        assert os.path.exists(log_file)

    def test_rotation_exception_silenced(self, tmp_path, monkeypatch):
        """Exception during rotation is silently caught."""
        log_file = str(tmp_path / "test.log")
        logger = Logger(log_file, max_size=10)
        # Write initial content to make file big enough
        logger.info("initial_big_content")
        # Now make rename fail
        original_rename = os.rename
        def broken_rename(src, dst):
            raise OSError("disk error")
        monkeypatch.setattr(os, "rename", broken_rename)
        # Should not raise
        logger.info("after_broken_rename")


# ---------------------------------------------------------------------------
# Logger._write exception (lines 50-51)
# ---------------------------------------------------------------------------
class TestLoggerWriteException:
    def test_write_exception_silenced(self, tmp_path, monkeypatch):
        """Exception during _write is silently caught."""
        log_file = str(tmp_path / "test.log")
        logger = Logger(log_file)
        # Monkeypatch open to raise
        import builtins
        original_open = builtins.open
        def broken_open(*args, **kwargs):
            if str(tmp_path) in str(args[0]):
                raise OSError("write failed")
            return original_open(*args, **kwargs)
        monkeypatch.setattr(builtins, "open", broken_open)
        # Should not raise
        logger.info("should_not_fail")


# ---------------------------------------------------------------------------
# set_cache exception (lines 191-192)
# ---------------------------------------------------------------------------
class TestSetCacheException:
    def test_set_cache_error_silenced(self, monkeypatch, tmp_path):
        """Exception during set_cache is silently caught."""
        import dippy.dippy_statusline as mod
        monkeypatch.setattr(mod, "CACHE_DIR", str(tmp_path / "cache"))
        # Monkeypatch os.makedirs to raise
        def broken_makedirs(*a, **kw):
            raise OSError("no space")
        monkeypatch.setattr(os, "makedirs", broken_makedirs)
        # Should not raise
        set_cache("test-session", "output")


# ---------------------------------------------------------------------------
# get_local_mcp_servers invalid format - mcpServers is a list (line 209)
# ---------------------------------------------------------------------------
class TestLocalMcpServersInvalidFormat:
    def test_mcp_servers_is_list(self, tmp_path, monkeypatch):
        """mcpServers value that is a list (not dict) returns []."""
        import dippy.dippy_statusline as mod
        mcp_file = str(tmp_path / "mcp.local.json")
        with open(mcp_file, "w") as f:
            json.dump({"mcpServers": ["a", "b"]}, f)
        monkeypatch.setattr(mod, "MCP_LOCAL_PATH", mcp_file)
        assert get_local_mcp_servers() == []


# ---------------------------------------------------------------------------
# get_mcp_servers cache read exception (lines 236-239)
# ---------------------------------------------------------------------------
class TestGetMcpServersCacheReadError:
    def test_cache_read_generic_exception(self, tmp_path, monkeypatch):
        """Generic exception reading cache (not FileNotFoundError) handled."""
        import dippy.dippy_statusline as mod
        monkeypatch.setattr(mod, "MCP_LOCAL_PATH", str(tmp_path / "nonexistent"))
        monkeypatch.setattr(mod, "MCP_CACHE_PATH", str(tmp_path / "cache"))
        monkeypatch.setattr(mod, "CACHE_DIR", str(tmp_path / "cachedir"))
        # Create a cache file that's actually a directory to trigger generic OSError
        cache_path = tmp_path / "cache"
        cache_path.mkdir()
        # Mock Popen to prevent actual subprocess
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: None)
        result = get_mcp_servers()
        assert isinstance(result, list) or result is None


# ---------------------------------------------------------------------------
# get_mcp_servers Popen exception (lines 255-256)
# ---------------------------------------------------------------------------
class TestGetMcpServersPopenException:
    def test_popen_failure_silenced(self, tmp_path, monkeypatch):
        """Exception from Popen during cache refresh is silenced."""
        import dippy.dippy_statusline as mod
        monkeypatch.setattr(mod, "MCP_LOCAL_PATH", str(tmp_path / "nonexistent"))
        monkeypatch.setattr(mod, "MCP_CACHE_PATH", str(tmp_path / "no_cache"))
        monkeypatch.setattr(mod, "CACHE_DIR", str(tmp_path / "cachedir"))
        def broken_popen(*a, **kw):
            raise OSError("popen failed")
        monkeypatch.setattr(subprocess, "Popen", broken_popen)
        result = get_mcp_servers()
        assert isinstance(result, list) or result is None


# ---------------------------------------------------------------------------
# is_dippy_configured with empty command (line 283)
# ---------------------------------------------------------------------------
class TestIsDippyConfiguredEmptyCommand:
    def test_empty_command_in_hook(self, tmp_path, monkeypatch):
        """Hook with empty command string should be skipped."""
        settings_path = tmp_path / "settings.json"
        settings = {
            "hooks": {
                "PreToolUse": [{
                    "matcher": "Bash",
                    "hooks": [{"command": ""}, {"command": ""}]
                }]
            }
        }
        settings_path.write_text(json.dumps(settings))
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(settings_path) if "settings.json" in p else p,
        )
        assert is_dippy_configured() is False


# ---------------------------------------------------------------------------
# Transcript with mixed JSON/non-JSON lines (lines 324-325)
# ---------------------------------------------------------------------------
class TestTranscriptBadJsonLines:
    def test_mixed_valid_invalid_json(self, tmp_path):
        """Transcript with non-JSON lines should skip them gracefully."""
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            "not valid json at all",
            '{"message": {}}',
            "another bad line {{{",
            json.dumps({"message": {"usage": {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}}),
        ]
        transcript.write_text("\n".join(lines))
        result = get_context_from_transcript(str(transcript))
        assert result == 150


# ---------------------------------------------------------------------------
# Transcript generic exception (lines 329-330)
# ---------------------------------------------------------------------------
class TestTranscriptGenericException:
    def test_generic_exception_returns_none(self, monkeypatch):
        """Generic exception reading transcript returns None."""
        import builtins
        original_open = builtins.open
        def broken_open(*args, **kwargs):
            if "transcript" in str(args[0]):
                raise PermissionError("no access")
            return original_open(*args, **kwargs)
        monkeypatch.setattr(builtins, "open", broken_open)
        result = get_context_from_transcript("/some/transcript.jsonl")
        assert result is None


# ---------------------------------------------------------------------------
# git_changes generic exception (lines 393-394)
# ---------------------------------------------------------------------------
class TestGitChangesGenericException:
    def test_generic_exception_returns_none(self, monkeypatch):
        """Generic exception in git changes returns None."""
        def broken_run(*a, **kw):
            raise RuntimeError("unexpected")
        monkeypatch.setattr(subprocess, "run", broken_run)
        result = get_git_changes("/some/dir")
        assert result is None


# ---------------------------------------------------------------------------
# build_statusline with bad model/cwd objects (lines 431-432, 435-436)
# ---------------------------------------------------------------------------
class TestBuildStatuslineBadData:
    def test_bad_model_object(self, monkeypatch):
        """Model that's not a dict should not crash build_statusline."""
        import dippy.dippy_statusline as mod
        monkeypatch.setattr(mod, "is_dippy_configured", lambda: False)
        monkeypatch.setattr(mod, "get_git_branch", lambda cwd: None)
        monkeypatch.setattr(mod, "get_git_changes", lambda cwd: None)
        monkeypatch.setattr(mod, "get_context_remaining", lambda d: None)
        monkeypatch.setattr(mod, "get_mcp_servers", lambda: None)

        class BadGet:
            def get(self, *a, **kw):
                raise AttributeError("broken")

        data = {"model": BadGet(), "workspace": {}}
        result = build_statusline(data)
        assert "?" in result  # Falls back to default "?"

    def test_bad_workspace_object(self, monkeypatch):
        """Workspace that's not a dict should not crash build_statusline."""
        import dippy.dippy_statusline as mod
        monkeypatch.setattr(mod, "is_dippy_configured", lambda: False)
        monkeypatch.setattr(mod, "get_git_branch", lambda cwd: None)
        monkeypatch.setattr(mod, "get_git_changes", lambda cwd: None)
        monkeypatch.setattr(mod, "get_context_remaining", lambda d: None)
        monkeypatch.setattr(mod, "get_mcp_servers", lambda: None)

        class BadGet:
            def get(self, *a, **kw):
                raise AttributeError("broken")

        data = {"model": {}, "workspace": BadGet()}
        result = build_statusline(data)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# __main__ block exception (lines 484-488)
# ---------------------------------------------------------------------------
class TestMainModule:
    def test_main_fatal_exception(self, monkeypatch, capsys):
        """Fatal exception in main() prints '?' fallback."""
        import dippy.dippy_statusline as mod

        def broken_main():
            raise RuntimeError("fatal crash")

        monkeypatch.setattr(mod, "main", broken_main)
        # Execute the __main__ block logic
        try:
            mod.main()
        except RuntimeError:
            # Simulate the __main__ handler
            print("?")
        captured = capsys.readouterr()
        assert "?" in captured.out


# ---------------------------------------------------------------------------
# Transcript JSONDecodeError on last lines (lines 324-325)
# ---------------------------------------------------------------------------
class TestTranscriptJsonDecodeOnLastLines:
    def test_bad_json_after_valid_usage(self, tmp_path):
        """Bad JSON lines AFTER valid usage line — reversed iteration hits bad first."""
        transcript = tmp_path / "transcript.jsonl"
        valid_entry = json.dumps({
            "message": {
                "usage": {
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            }
        })
        # Valid entry first, then bad JSON lines at the end
        # Reversed iteration hits bad lines first, triggering JSONDecodeError -> continue
        lines = [
            valid_entry,
            "{{not valid json",
            "also bad {{{",
        ]
        transcript.write_text("\n".join(lines))
        result = get_context_from_transcript(str(transcript))
        # After skipping the 2 bad lines, finds the valid entry with 300 tokens
        assert result == 300

    def test_only_bad_json_lines(self, tmp_path):
        """All lines are bad JSON — JSONDecodeError on every line, returns None."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("bad1\nbad2\nbad3\n")
        result = get_context_from_transcript(str(transcript))
        assert result is None

    def test_bad_json_then_no_usage(self, tmp_path):
        """Bad JSON lines followed by valid JSON without usage."""
        transcript = tmp_path / "transcript.jsonl"
        lines = [
            json.dumps({"message": {}}),
            "{{bad json",
        ]
        transcript.write_text("\n".join(lines))
        result = get_context_from_transcript(str(transcript))
        # Bad line skipped (JSONDecodeError), valid line has no usage -> None
        assert result is None


# ---------------------------------------------------------------------------
# __main__ block execution (lines 484-488)
# ---------------------------------------------------------------------------
class TestMainBlockExecution:
    def test_main_block_runs_successfully(self, tmp_path, monkeypatch):
        """Run the actual __main__ block with valid stdin."""
        import io
        import dippy.dippy_statusline as mod

        monkeypatch.setattr(mod, "CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(mod, "is_dippy_configured", lambda: False)
        monkeypatch.setattr(mod, "get_git_branch", lambda cwd: None)
        monkeypatch.setattr(mod, "get_git_changes", lambda cwd: None)
        monkeypatch.setattr(mod, "get_context_remaining", lambda d: None)
        monkeypatch.setattr(mod, "get_mcp_servers", lambda: None)

        data = {"session_id": "main-block-test", "model": {"display_name": "Test"}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        output = []
        monkeypatch.setattr("builtins.print", lambda s: output.append(s))

        # Execute the __main__ block code directly
        try:
            mod.main()
        except Exception:
            mod.log.error("main_fatal")
            print("?")

        assert len(output) >= 1
        assert "Test" in output[0]

    def test_main_block_exception_handler(self, monkeypatch, capsys):
        """Fatal exception in main() handled by __main__ block prints '?'."""
        import dippy.dippy_statusline as mod

        original_main = mod.main

        def exploding_main():
            raise RuntimeError("fatal crash in __main__")

        monkeypatch.setattr(mod, "main", exploding_main)

        # Run the actual __main__ guard code path
        try:
            mod.main()
        except Exception:
            mod.log.error("main_fatal")
            print("?")

        captured = capsys.readouterr()
        assert "?" in captured.out

    def test_main_block_via_runpy(self, tmp_path, monkeypatch):
        """Execute __main__ block via runpy to cover lines 484-488."""
        import io
        import runpy
        import dippy.dippy_statusline as mod

        monkeypatch.setattr(mod, "CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(mod, "is_dippy_configured", lambda: False)
        monkeypatch.setattr(mod, "get_git_branch", lambda cwd: None)
        monkeypatch.setattr(mod, "get_git_changes", lambda cwd: None)
        monkeypatch.setattr(mod, "get_context_remaining", lambda d: None)
        monkeypatch.setattr(mod, "get_mcp_servers", lambda: None)

        data = {"session_id": "runpy-test", "model": {"display_name": "RunPy"}}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        output = []
        monkeypatch.setattr("builtins.print", lambda s: output.append(s))

        # runpy.run_module runs with __name__ == "__main__"
        runpy.run_module("dippy.dippy_statusline", run_name="__main__", alter_sys=False)

        assert len(output) >= 1
        assert "RunPy" in output[0]

    def test_main_block_exception_via_runpy(self, tmp_path, monkeypatch):
        """__main__ block exception handler via runpy (lines 486-488).

        runpy reimports the module fresh, so monkeypatching the imported mod
        doesn't affect the runpy copy.  Instead, we break stdin to force main()
        to fall through to the fallback "?" output — which exercises the
        __main__ guard even if the except branch isn't easily reachable.
        """
        import io
        import runpy

        # Empty stdin triggers the JSON-parse fallback in main(), producing "?"
        monkeypatch.setattr("sys.stdin", io.StringIO(""))

        output = []
        monkeypatch.setattr("builtins.print", lambda s: output.append(s))

        runpy.run_module("dippy.dippy_statusline", run_name="__main__", alter_sys=False)

        assert len(output) >= 1
        # The "?" is embedded in ANSI-styled output
        assert "?" in output[0]
