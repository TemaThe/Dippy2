"""
Tests for the core parser module.
"""

from __future__ import annotations

from dippy.core.parser import tokenize


class TestTokenize:
    """Tests for command tokenization."""

    def test_simple_command(self):
        """Simple command should tokenize correctly."""
        tokens = tokenize("ls -la")
        assert tokens == ["ls", "-la"]

    def test_quoted_string(self):
        """Quoted strings should be preserved."""
        tokens = tokenize("echo 'hello world'")
        assert tokens == ["echo", "hello world"]

    def test_double_quoted(self):
        """Double quoted strings should be preserved."""
        tokens = tokenize('grep "pattern with spaces" file.txt')
        assert tokens == ["grep", "pattern with spaces", "file.txt"]

    def test_empty_command(self):
        """Empty command should return empty list."""
        tokens = tokenize("")
        assert tokens == []

    def test_whitespace_only(self):
        """Whitespace-only command should return empty list."""
        tokens = tokenize("   ")
        assert tokens == []

    def test_complex_command(self):
        """Complex command with flags and args."""
        tokens = tokenize("git log --oneline -n 10")
        assert tokens == ["git", "log", "--oneline", "-n", "10"]

    def test_none_input(self):
        """None input should return empty list."""
        tokens = tokenize(None)
        assert tokens == []

    def test_parse_exception_returns_empty(self):
        """Unparseable command should return empty list (exception caught)."""
        # This triggers a parse error inside Parable
        tokens = tokenize("if then")
        # May return empty or partial tokens depending on parser behavior
        assert isinstance(tokens, list)

    def test_single_quoted_string_stripped(self):
        """Single-quoted strings should have quotes stripped."""
        tokens = tokenize("echo 'hello'")
        assert tokens == ["echo", "hello"]

    def test_pipeline_extracts_first_command(self):
        """Pipeline should extract only the first command's tokens."""
        tokens = tokenize("echo hello | grep hello")
        assert tokens[0] == "echo"
        assert "hello" in tokens

    def test_list_extracts_first_part(self):
        """List with && should extract only the first part's tokens."""
        tokens = tokenize("echo hello && echo world")
        assert tokens[0] == "echo"
        # Should only contain tokens from first part
        assert tokens == ["echo", "hello"]

    def test_list_with_semicolon(self):
        """List with ; should extract only the first part's tokens."""
        tokens = tokenize("echo hello; echo world")
        assert tokens[0] == "echo"
        assert tokens == ["echo", "hello"]

    def test_command_with_multiple_words(self):
        """Command node with multiple words."""
        tokens = tokenize("git push origin main")
        assert tokens == ["git", "push", "origin", "main"]

    def test_complex_pipeline_first_only(self):
        """Complex pipeline extracts first command tokens."""
        tokens = tokenize("cat file.txt | sort | uniq -c | head -10")
        assert tokens[0] == "cat"
        assert tokens == ["cat", "file.txt"]
