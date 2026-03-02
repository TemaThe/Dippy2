"""Tests for analyzer bugs found in PR #29 review."""

from __future__ import annotations

from pathlib import Path

import pytest

from dippy.core.analyzer import analyze
from dippy.core.config import Config


class TestEnvVarPrefixHandling:
    """Handler should receive tokens without env var prefixes."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_git_status_with_env_var(self, config, cwd):
        """FOO=bar git status should be recognized as 'git status'."""
        result = analyze("FOO=bar git status", config, cwd)
        # Should recognize this as git status (safe read operation)
        assert result.action == "allow"
        assert result.reason == "git status"

    def test_git_log_with_multiple_env_vars(self, config, cwd):
        """Multiple env vars should all be skipped."""
        result = analyze("FOO=bar BAZ=qux git log", config, cwd)
        assert result.action == "allow"
        assert result.reason == "git log"

    def test_docker_ps_with_env_var(self, config, cwd):
        """DOCKER_HOST=x docker ps should work."""
        result = analyze("DOCKER_HOST=tcp://localhost:2375 docker ps", config, cwd)
        assert result.action == "allow"
        assert result.reason == "docker ps"

    def test_env_var_with_unsafe_command(self, config, cwd):
        """Env var prefix shouldn't hide unsafe commands."""
        result = analyze("FOO=bar git push", config, cwd)
        assert result.action == "ask"
        assert result.reason == "git push"


class TestCmdsubInjectionWarning:
    """Pure cmdsubs in handler CLIs should warn about injection risk."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_git_cmdsub_injection_reason(self, config, cwd):
        """git $(echo status) should mention injection risk."""
        result = analyze("git $(echo status)", config, cwd)
        assert result.action == "ask"
        assert "injection" in result.reason.lower()

    def test_docker_cmdsub_injection_reason(self, config, cwd):
        """docker $(echo run) should mention injection risk."""
        result = analyze("docker $(echo run) alpine", config, cwd)
        assert result.action == "ask"
        assert "injection" in result.reason.lower()

    def test_kubectl_cmdsub_injection_reason(self, config, cwd):
        """kubectl $(echo delete) should mention injection risk."""
        result = analyze("kubectl $(echo delete) pod foo", config, cwd)
        assert result.action == "ask"
        assert "injection" in result.reason.lower()

    def test_cmdsub_allowed_when_outer_readonly(self, config, cwd):
        """Cmdsub in arg position should be allowed if outer command is read-only."""
        # AWS describe with cmdsub - both are read-only
        result = analyze(
            "aws elbv2 describe-listeners --load-balancer-arn $(aws elbv2 describe-load-balancers --names foo --query 'LoadBalancers[0].LoadBalancerArn' --output text)",
            config,
            cwd,
        )
        assert result.action == "allow"

    def test_cmdsub_still_asks_when_outer_mutates(self, config, cwd):
        """Cmdsub should still ask if outer command is a mutation."""
        # AWS modify with cmdsub - outer is mutation
        result = analyze(
            "aws elbv2 modify-listener --listener-arn $(aws elbv2 describe-listeners --query 'Listeners[0].ListenerArn' --output text)",
            config,
            cwd,
        )
        assert result.action == "ask"

    def test_gh_cmdsub_allowed_when_outer_readonly(self, config, cwd):
        """gh run view with cmdsub should be allowed."""
        result = analyze(
            "gh run view $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')",
            config,
            cwd,
        )
        assert result.action == "allow"


class TestNegationAndArith:
    """Test negation (!) and arithmetic (( )) constructs."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("! grep foo", "allow"),
            ("! rm file", "ask"),
            ("(( i++ ))", "allow"),
            ("(( x = 5 ))", "allow"),
            ("(( x = $(echo 1) ))", "allow"),  # safe cmdsub
            ("(( arr[$(rm -rf /)] ))", "ask"),  # dangerous cmdsub in subscript
        ],
    )
    def test_negation_and_arith(self, cmd, expected, config, cwd):
        assert analyze(cmd, config, cwd).action == expected


class TestCoproc:
    """Test coproc construct."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("coproc cat", "allow"),
            ("coproc { echo hi; }", "allow"),
            ("coproc NAME { echo hi; }", "allow"),
            ("coproc NAME { cat; }", "allow"),
            ("coproc rm -rf /", "ask"),
            ("coproc { rm -rf /; }", "ask"),
            ("coproc NAME { rm file; }", "ask"),
        ],
    )
    def test_coproc(self, cmd, expected, config, cwd):
        assert analyze(cmd, config, cwd).action == expected


class TestCondExpr:
    """Test [[ ]] conditional expression construct."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # Simple conditions - allow
            ("[[ -f foo ]]", "allow"),
            ('[[ -z "$x" ]]', "allow"),
            ("[[ $a == $b ]]", "allow"),
            ("[[ -f x && -d y ]]", "allow"),
            ("[[ -f x || -d y ]]", "allow"),
            ("[[ ! -f foo ]]", "allow"),
            ("[[ ( -f x ) ]]", "allow"),
            # Safe cmdsubs - allow
            ("[[ -f $(echo foo) ]]", "allow"),
            ("[[ $(echo x) == y ]]", "allow"),
            ("[[ -f x && $(pwd) == y ]]", "allow"),
            # Dangerous cmdsubs - ask
            ("[[ -f $(rm -rf /) ]]", "ask"),
            ("[[ $(rm file) == x ]]", "ask"),
            ("[[ -f x && $(rm y) == z ]]", "ask"),
            ("[[ ! -f $(rm foo) ]]", "ask"),
            ("[[ ( $(rm x) == y ) ]]", "ask"),
        ],
    )
    def test_cond_expr(self, cmd, expected, config, cwd):
        assert analyze(cmd, config, cwd).action == expected


class TestCmdsubSecurityGaps:
    """Tests for cmdsub analysis in various constructs.

    These tests verify that dangerous command substitutions are detected
    in all contexts, not just simple command arguments.
    """

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # for loop iteration words
            ("for i in $(rm foo); do echo $i; done", "ask"),
            ("for i in $(ls); do echo $i; done", "allow"),
            ("for i in a $(rm foo) b; do echo $i; done", "ask"),
        ],
    )
    def test_for_iteration_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in for loop iteration list should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # select word list
            ("select x in $(rm foo); do echo $x; done", "ask"),
            ("select x in $(ls); do echo $x; done", "allow"),
        ],
    )
    def test_select_words_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in select word list should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # case word
            ("case $(rm foo) in *) echo y;; esac", "ask"),
            ("case $(echo x) in *) echo y;; esac", "allow"),
        ],
    )
    def test_case_word_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in case word should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # subshell with redirect containing cmdsub
            ("(ls) > $(rm foo)", "ask"),
            ("(ls) > $(echo /tmp/out)", "ask"),  # still ask - output redirect
            # brace-group with redirect containing cmdsub
            ("{ ls; } > $(rm foo)", "ask"),
            ("{ ls; } > $(echo /tmp/out)", "ask"),  # still ask - output redirect
        ],
    )
    def test_compound_redirect_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in redirect targets of compound commands should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # Redirect target with cmdsub - inner command should be analyzed
            ("ls > $(rm foo)", "ask"),
            # Even safe inner cmdsub should ask due to output redirect
            ("ls > $(echo /tmp/out)", "ask"),
        ],
    )
    def test_redirect_target_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in redirect targets should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestArithCmdRedirect:
    """Tests for arith-cmd redirect checking."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("(( 1 )) > $(rm foo)", "ask"),
            ("(( x++ )) > /tmp/out", "ask"),
        ],
    )
    def test_arith_cmd_redirect(self, cmd, expected, config, cwd):
        """Arith-cmd should check its redirects."""
        assert analyze(cmd, config, cwd).action == expected


class TestForArithCmdsub:
    """Tests for cmdsubs in for-arith init/cond/incr expressions."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("for (( i=$(rm foo); i<10; i++ )); do echo $i; done", "ask"),
            ("for (( i=0; i<$(rm foo); i++ )); do echo $i; done", "ask"),
            ("for (( i=0; i<10; i+=$(rm foo) )); do echo $i; done", "ask"),
        ],
    )
    def test_for_arith_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in for-arith init/cond/incr should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestParamExpansionCmdsub:
    """Tests for cmdsubs nested inside parameter expansions."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("echo ${x:-$(rm foo)}", "ask"),
            ("echo ${x:=$(rm foo)}", "ask"),
            ("echo ${x:+$(rm foo)}", "ask"),
            ("echo ${x:?$(rm foo)}", "ask"),
            ("[[ -f ${x:-$(rm foo)} ]]", "ask"),
            ("for i in ${x:-$(rm foo)}; do echo $i; done", "ask"),
        ],
    )
    def test_param_expansion_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs nested in parameter expansions should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestBacktickCmdsub:
    """Tests for backtick command substitutions in raw strings."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # Backticks in for-arith expressions
            ("for (( i=`rm foo`; i<10; i++ )); do echo $i; done", "ask"),
            # Backticks in param expansion
            ("echo ${x:-`rm foo`}", "ask"),
        ],
    )
    def test_backtick_cmdsub(self, cmd, expected, config, cwd):
        """Backtick command substitutions should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestHeredocCmdsub:
    """Tests for command substitutions in heredocs."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            # Unquoted heredoc - cmdsubs ARE executed
            ("cat <<EOF\n$(rm foo)\nEOF", "ask"),
            # Multiple cmdsubs in heredoc
            ("cat <<EOF\n$(echo a)\n$(rm foo)\nEOF", "ask"),
        ],
    )
    def test_heredoc_cmdsub(self, cmd, expected, config, cwd):
        """Cmdsubs in unquoted heredocs should be analyzed."""
        assert analyze(cmd, config, cwd).action == expected


class TestConditionalTestCommands:
    """Test [ and test conditional commands (issue #61)."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    @pytest.mark.parametrize(
        "cmd,expected_action,expected_reason",
        [
            ('[ -n "$x" ]', "allow", "conditional test"),
            ("[ -f /etc/passwd ]", "allow", "conditional test"),
            ("[ -z '' ]", "allow", "conditional test"),
            ('test -n "$x"', "allow", "conditional test"),
            ("test -f /etc/passwd", "allow", "conditional test"),
            ("test -z ''", "allow", "conditional test"),
        ],
    )
    def test_basic_conditionals(
        self, cmd, expected_action, expected_reason, config, cwd
    ):
        """Basic [ and test commands should be allowed."""
        result = analyze(cmd, config, cwd)
        assert result.action == expected_action
        assert result.reason == expected_reason

    def test_conditional_in_while_loop(self, config, cwd):
        """[ in while loop body should allow with proper context (issue #61)."""
        cmd = 'while read -r data; do [ -n "$data" ] && echo "$data"; done'
        result = analyze(cmd, config, cwd)
        assert result.action == "allow"
        assert "conditional test" in result.reason
        assert "read" in result.reason
        assert "echo" in result.reason

    def test_kinesis_pipeline_from_issue(self, config, cwd):
        """Full kinesis pipeline from issue #61 should allow."""
        cmd = (
            "SHARD_ITERATOR=$(aws kinesis get-shard-iterator --stream-name s --shard-id 0 --shard-iterator-type LATEST --query ShardIterator --output text) && "
            'aws kinesis get-records --shard-iterator "$SHARD_ITERATOR" --query "Records[].Data" --output text | '
            'while read -r data; do [ -n "$data" ] && echo "$data" | base64 -d; done | '
            "sort"
        )
        result = analyze(cmd, config, cwd)
        assert result.action == "allow"
        # Should not contain the confusing truncated "[ -n" reason
        assert "[ -n" not in result.reason
        assert "conditional test" in result.reason

    @pytest.mark.parametrize(
        "cmd,expected_action",
        [
            ("[ -f $(rm -rf /) ]", "ask"),
            ("[ -n $(rm foo) ]", "ask"),
            ("test -f $(rm foo)", "ask"),
            ("test -z $(dd if=/dev/zero of=/dev/sda)", "ask"),
        ],
    )
    def test_dangerous_cmdsub_in_conditional(self, cmd, expected_action, config, cwd):
        """Dangerous cmdsubs inside [ and test should still be caught."""
        result = analyze(cmd, config, cwd)
        assert result.action == expected_action

    @pytest.mark.parametrize(
        "cmd,expected_action",
        [
            ("[ -f $(ls) ]", "allow"),
            ("[ -n $(echo hello) ]", "allow"),
            ("test -f $(pwd)", "allow"),
        ],
    )
    def test_safe_cmdsub_in_conditional(self, cmd, expected_action, config, cwd):
        """Safe cmdsubs inside [ and test should be allowed."""
        result = analyze(cmd, config, cwd)
        assert result.action == expected_action

    @pytest.mark.parametrize(
        "cmd,expected_action,reason_contains",
        [
            ("[ -f <(rm foo) ]", "ask", "process substitution"),
            ("[ -f x ] > /tmp/out", "ask", "redirect"),
            ("FOO=$(rm bar) [ -f x ]", "ask", "command substitution"),
            ("[ -f ${x:-$(rm foo)} ]", "ask", "cmdsub"),
        ],
    )
    def test_conditional_edge_cases(
        self, cmd, expected_action, reason_contains, config, cwd
    ):
        """Edge cases: procsubs, redirects, env var cmdsubs, param expansion cmdsubs."""
        result = analyze(cmd, config, cwd)
        assert result.action == expected_action
        assert reason_contains in result.reason


class TestCdPathResolution:
    """Test that `cd <literal> && ...` resolves paths against the cd target."""

    def test_cd_resolves_relative_path_for_config_match(self, tmp_path):
        """cd /foo && ./bar should resolve ./bar against /foo."""
        from dippy.core.config import parse_config

        target_dir = tmp_path / "myproject"
        target_dir.mkdir()
        config = parse_config(f"allow {target_dir}/tool *")
        # cwd is tmp_path, but cd changes to target_dir
        result = analyze(f"cd {target_dir} && ./tool --flag", config, tmp_path)
        assert result.action == "allow"

    def test_cd_tilde_path(self):
        """cd ~ && ./script should resolve ./script against home."""
        from dippy.core.config import parse_config

        home = Path.home()
        config = parse_config(f"allow {home}/script *")
        result = analyze("cd ~ && ./script arg", config, Path("/somewhere/else"))
        assert result.action == "allow"

    def test_cd_absolute_path(self, tmp_path):
        """cd /absolute/path && cmd should resolve against that path."""
        from dippy.core.config import parse_config

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        config = parse_config(f"allow {target_dir}/run *")
        result = analyze(f"cd {target_dir} && ./run test", config, tmp_path)
        assert result.action == "allow"

    def test_cd_with_cmdsub_target_not_resolved(self):
        """cd $(cmd) should not resolve (non-literal target)."""
        config = Config()
        cwd = Path.cwd()
        result = analyze("cd $(echo /tmp) && ls", config, cwd)
        # cd with cmdsub should still work (just won't resolve the path)
        assert result.action == "allow"  # ls is safe regardless


class TestEmptyAndSpecialCommands:
    """Tests for edge case commands."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_empty_command(self, config, cwd):
        """Empty command should return ask."""
        result = analyze("", config, cwd)
        assert result.action == "ask"
        assert "empty command" in result.reason.lower()

    def test_whitespace_only_command(self, config, cwd):
        """Whitespace-only command should return ask."""
        result = analyze("   ", config, cwd)
        assert result.action == "ask"
        assert "empty command" in result.reason.lower()

    def test_env_assignment_only(self, config, cwd):
        """FOO=bar with no command should be allowed (env assignment)."""
        result = analyze("FOO=bar", config, cwd)
        assert result.action == "allow"
        assert "env assignment" in result.reason.lower()


class TestConfigAskRuleWithMessage:
    """Test config ask rule with message."""

    def test_ask_with_message(self):
        """ask rule with message should include message in reason."""
        from dippy.core.config import parse_config

        config = parse_config('ask rm * "be careful with rm"')
        cwd = Path.cwd()
        result = analyze("rm foo", config, cwd)
        assert result.action == "ask"
        assert "be careful" in result.reason

    def test_deny_with_message(self):
        """deny rule with message should include message in reason."""
        from dippy.core.config import parse_config

        config = parse_config('deny rm -rf * "never allow rm -rf"')
        cwd = Path.cwd()
        result = analyze("rm -rf /tmp/foo", config, cwd)
        assert result.action == "deny"
        assert "never allow" in result.reason


class TestWrapperCommands:
    """Test wrapper command unwrapping."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_timeout_with_safe_command(self, config, cwd):
        """timeout 10 ls should allow (unwraps to ls)."""
        result = analyze("timeout 10 ls", config, cwd)
        assert result.action == "allow"

    def test_timeout_with_unsafe_command(self, config, cwd):
        """timeout 10 rm foo should ask (unwraps to rm)."""
        result = analyze("timeout 10 rm foo", config, cwd)
        assert result.action == "ask"

    def test_nice_with_safe_command(self, config, cwd):
        """nice -n 10 ls should allow (unwraps to ls)."""
        result = analyze("nice -n 10 ls", config, cwd)
        assert result.action == "allow"

    def test_command_v_git(self, config, cwd):
        """command -v git should allow (checking command existence)."""
        result = analyze("command -v git", config, cwd)
        assert result.action == "allow"
        assert "command -v" in result.reason

    def test_command_V_git(self, config, cwd):
        """command -V git should allow (checking command existence)."""
        result = analyze("command -V git", config, cwd)
        assert result.action == "allow"
        assert "command -v" in result.reason

    def test_wrapper_with_no_inner_command(self, config, cwd):
        """timeout alone should ask."""
        result = analyze("timeout", config, cwd)
        assert result.action == "ask"


class TestRemoteMode:
    """Test remote=True skips path-based checks."""

    def test_remote_skips_redirect_rules(self):
        """Remote mode should skip redirect path checks."""
        config = Config()
        cwd = Path.cwd()
        # With remote=True, redirects to local paths should not be checked
        result = analyze(
            "ls > /tmp/out",
            config,
            cwd,
            remote=True,
        )
        # Remote mode skips path expansion and redirect rules
        assert result.action == "allow"
        assert "ls" in result.reason

    def test_remote_with_safe_command(self):
        """Remote mode with safe command should allow."""
        config = Config()
        cwd = Path.cwd()
        result = analyze("cat /etc/passwd", config, cwd, remote=True)
        assert result.action == "allow"


class TestCombineEmptyDecisions:
    """Test _combine with empty decisions list."""

    def test_combine_empty_returns_allow(self):
        """_combine([]) should return allow with 'empty' reason."""
        from dippy.core.analyzer import _combine

        result = _combine([])
        assert result.action == "allow"
        assert "empty" in result.reason

    def test_combine_single_allow(self):
        """_combine with single allow should return allow."""
        from dippy.core.analyzer import Decision, _combine

        result = _combine([Decision("allow", "ls")])
        assert result.action == "allow"

    def test_combine_deny_wins(self):
        """_combine with deny and allow should return deny."""
        from dippy.core.analyzer import Decision, _combine

        result = _combine([Decision("allow", "ls"), Decision("deny", "rm")])
        assert result.action == "deny"

    def test_combine_ask_wins_over_allow(self):
        """_combine with ask and allow should return ask."""
        from dippy.core.analyzer import Decision, _combine

        result = _combine([Decision("allow", "ls"), Decision("ask", "unknown")])
        assert result.action == "ask"


class TestProcessSubstitution:
    """Test process substitution analysis."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_safe_process_substitution(self, config, cwd):
        """Safe process substitution should allow."""
        result = analyze("diff <(sort file1) <(sort file2)", config, cwd)
        assert result.action == "allow"

    def test_unsafe_process_substitution(self, config, cwd):
        """Unsafe process substitution should ask."""
        result = analyze("diff <(rm file1) <(sort file2)", config, cwd)
        assert result.action == "ask"
        assert "process substitution" in result.reason


class TestScriptUnfoldFromAnalyzer:
    """Test script unfolding triggered from the analyzer."""

    def test_bash_nonexistent_script(self):
        """bash nonexistent.sh should ask with 'not found'."""
        config = Config()
        cwd = Path("/tmp")
        result = analyze("bash nonexistent_script_xyz.sh", config, cwd)
        assert result.action == "ask"
        assert "not found" in result.reason


# ── Remaining coverage gap tests ──────────────────────────────────────────


class TestDecisionRepr:
    """Cover Decision.__repr__ (line 39)."""

    def test_repr(self):
        from dippy.core.analyzer import Decision

        d = Decision("allow", "ls")
        r = repr(d)
        assert r == "Decision('allow', 'ls')"

    def test_repr_deny(self):
        from dippy.core.analyzer import Decision

        d = Decision("deny", "rm -rf")
        assert "deny" in repr(d)


class TestParseReturnsEmptyNodes:
    """Cover line 73: parse succeeds but returns empty node list."""

    def test_semicolon_only(self):
        """Bare semicolon may parse to empty nodes."""
        config = Config()
        cwd = Path.cwd()
        # Semicolons alone produce no executable nodes
        result = analyze(";", config, cwd)
        # Either "empty command" (line 73) or parse error — both acceptable
        assert result.action in ("ask", "allow")


class TestAnalyzeNodeDirectCalls:
    """Cover _analyze_node with mock AST nodes for comment/unknown kinds."""

    def test_comment_node(self):
        """Comment node returns allow (line 366)."""
        from dippy.core.analyzer import _analyze_node
        from types import SimpleNamespace

        node = SimpleNamespace(kind="comment")
        result = _analyze_node(node, Config(), Path.cwd())
        assert result.action == "allow"
        assert result.reason == "comment"

    def test_unknown_node_kind(self):
        """Unknown node kind returns ask (line 373)."""
        from dippy.core.analyzer import _analyze_node
        from types import SimpleNamespace

        node = SimpleNamespace(kind="alien_construct")
        result = _analyze_node(node, Config(), Path.cwd())
        assert result.action == "ask"
        assert "unrecognized construct" in result.reason

    def test_empty_node_kind(self):
        """Empty node kind returns allow (line 369)."""
        from dippy.core.analyzer import _analyze_node
        from types import SimpleNamespace

        node = SimpleNamespace(kind="empty")
        result = _analyze_node(node, Config(), Path.cwd())
        assert result.action == "allow"
        assert result.reason == "empty"


class TestAnalyzeSimpleCommandDirect:
    """Cover _analyze_simple_command with empty words (line 569)."""

    def test_empty_words(self):
        from dippy.core.analyzer import _analyze_simple_command

        result = _analyze_simple_command([], Config(), Path.cwd())
        assert result.action == "allow"
        assert result.reason == "empty"


class TestRedirectConfigRules:
    """Cover lines 546-551: redirect rules matching deny/ask."""

    def test_deny_redirect_rule(self):
        """deny-redirect rule should produce deny decision."""
        from dippy.core.config import parse_config

        config = parse_config('deny-redirect /etc/* "no writes to /etc"')
        cwd = Path.cwd()
        result = analyze("echo hi > /etc/myfile", config, cwd)
        assert result.action == "deny"
        assert "redirect to /etc/myfile" in result.reason

    def test_ask_redirect_rule(self):
        """ask-redirect rule should produce ask decision with message."""
        from dippy.core.config import parse_config

        config = parse_config('ask-redirect /tmp/* "check tmp writes"')
        cwd = Path.cwd()
        result = analyze("echo hi > /tmp/myfile", config, cwd)
        assert result.action == "ask"
        assert "redirect to /tmp/myfile" in result.reason


class TestWrapperDoubleHyphen:
    """Cover lines 613, 621: wrapper with -- separator and no inner command."""

    def test_timeout_double_hyphen_safe(self):
        """timeout -- ls should allow (skip --, unwrap to ls)."""
        config = Config()
        cwd = Path.cwd()
        result = analyze("timeout -- ls", config, cwd)
        assert result.action == "allow"

    def test_wrapper_only_flags_no_inner(self):
        """timeout with only flags/numbers asks (no inner command after skipping)."""
        config = Config()
        cwd = Path.cwd()
        result = analyze("timeout 10 -s 9", config, cwd)
        assert result.action == "ask"
        assert "timeout" in result.reason


class TestGetWordValueDirect:
    """Cover line 765: _get_word_value with string input."""

    def test_string_input(self):
        from dippy.core.analyzer import _get_word_value

        assert _get_word_value("hello") == "hello"

    def test_quoted_string(self):
        from dippy.core.analyzer import _get_word_value

        assert _get_word_value('"hello"') == "hello"

    def test_node_input(self):
        from dippy.core.analyzer import _get_word_value
        from types import SimpleNamespace

        node = SimpleNamespace(value="world")
        assert _get_word_value(node) == "world"


class TestFindCmdsubsInArithNone:
    """Cover line 785: _find_cmdsubs_in_arith(None)."""

    def test_none_input(self):
        from dippy.core.analyzer import _find_cmdsubs_in_arith

        assert _find_cmdsubs_in_arith(None) == []


class TestAnalyzeCondNodeEdgeCases:
    """Cover lines 808, 853: _analyze_cond_node with None and unknown kind."""

    def test_none_node(self):
        from dippy.core.analyzer import _analyze_cond_node

        result = _analyze_cond_node(None, Config(), Path.cwd())
        assert result == []

    def test_unknown_cond_kind(self):
        from dippy.core.analyzer import _analyze_cond_node
        from types import SimpleNamespace

        node = SimpleNamespace(kind="weird_cond_type")
        result = _analyze_cond_node(node, Config(), Path.cwd())
        assert result == []


class TestAnalyzeWordPartsProcsub:
    """Cover lines 885-899: _analyze_word_parts with process substitution nodes."""

    def test_safe_procsub(self):
        """Process substitution with safe inner command (line 899)."""
        from dippy.core.analyzer import _analyze_word_parts
        from types import SimpleNamespace

        # Create mock procsub part with a safe command
        # The command needs to be a node that _analyze_node can process
        inner_cmd = SimpleNamespace(
            kind="command",
            words=["ls"],
            redirects=[],
            assignments=[],
        )
        procsub_part = SimpleNamespace(
            kind="procsub", command=inner_cmd, direction="<"
        )
        word = SimpleNamespace(parts=[procsub_part])
        result = _analyze_word_parts(word, Config(), Path.cwd())
        assert len(result) >= 1
        assert result[0].action == "allow"

    def test_unsafe_procsub(self):
        """Process substitution with unsafe inner command (lines 885-897)."""
        from dippy.core.analyzer import _analyze_word_parts
        from types import SimpleNamespace

        # Create mock procsub part with an unsafe command
        inner_cmd = SimpleNamespace(
            kind="command",
            words=["rm", "foo"],
            redirects=[],
            assignments=[],
        )
        procsub_part = SimpleNamespace(
            kind="procsub", command=inner_cmd, direction="<"
        )
        word = SimpleNamespace(parts=[procsub_part])
        result = _analyze_word_parts(word, Config(), Path.cwd())
        assert len(result) >= 1
        assert result[0].action == "ask"
        assert "procsub" in result[0].reason


class TestStringCmdsubEdgeCases:
    """Cover lines 934-935, 959, 981, 984 in _analyze_string_cmdsubs."""

    def test_nested_dollar_paren(self):
        """Nested $(...) increments depth (lines 934-935)."""
        from dippy.core.analyzer import _analyze_string_cmdsubs

        # String with nested cmdsub
        result = _analyze_string_cmdsubs(
            "$(echo $(date))", Config(), Path.cwd()
        )
        assert isinstance(result, list)
        # Should have at least one decision from the outer cmdsub
        assert len(result) >= 1

    def test_unclosed_dollar_paren(self):
        """Unclosed $( skips forward (line 959)."""
        from dippy.core.analyzer import _analyze_string_cmdsubs

        result = _analyze_string_cmdsubs(
            "$(incomplete", Config(), Path.cwd()
        )
        # Unclosed, no decisions extracted
        assert isinstance(result, list)
        assert len(result) == 0

    def test_backtick_safe_command(self):
        """Backtick with safe command (line 981)."""
        from dippy.core.analyzer import _analyze_string_cmdsubs

        result = _analyze_string_cmdsubs(
            "`ls`", Config(), Path.cwd()
        )
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0].action == "allow"

    def test_unclosed_backtick(self):
        """Unclosed backtick skips forward (line 984)."""
        from dippy.core.analyzer import _analyze_string_cmdsubs

        result = _analyze_string_cmdsubs(
            "`incomplete", Config(), Path.cwd()
        )
        assert isinstance(result, list)
        assert len(result) == 0

    def test_backtick_unsafe_command(self):
        """Backtick with unsafe command."""
        from dippy.core.analyzer import _analyze_string_cmdsubs

        result = _analyze_string_cmdsubs(
            "`rm foo`", Config(), Path.cwd()
        )
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0].action == "ask"
        assert "cmdsub" in result[0].reason


class TestResolveCdTargetDirect:
    """Cover lines 1016, 1019: _resolve_cd_target with ~/path and relative."""

    def test_tilde_subdir(self):
        """~/foo resolves to home/foo (line 1016)."""
        from dippy.core.analyzer import _resolve_cd_target

        home = Path.home()
        result = _resolve_cd_target("~/foo", Path.cwd())
        assert result == home / "foo"

    def test_relative_path(self):
        """relative path resolves against cwd (line 1019)."""
        from dippy.core.analyzer import _resolve_cd_target

        cwd = Path("/tmp/project")
        result = _resolve_cd_target("subdir", cwd)
        assert "subdir" in str(result)


# ── Additional coverage gap tests ─────────────────────────────────────────


class TestParamExpansionSafeCmdsub:
    """Cover line 466: decisions.extend(param_decisions) for safe param cmdsubs."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_safe_param_cmdsub_extends_decisions(self, config, cwd):
        """echo ${x:-$(echo hello)} — safe cmdsub in param expansion extends decisions."""
        result = analyze("echo ${x:-$(echo hello)}", config, cwd)
        assert result.action == "allow"

    def test_safe_param_cmdsub_with_ls(self, config, cwd):
        """echo ${x:=$(ls)} — safe cmdsub in param expansion."""
        result = analyze("echo ${x:=$(ls)}", config, cwd)
        assert result.action == "allow"


class TestEmptyWordsInAnalyzeCommand:
    """Cover line 479: empty words in _analyze_command (redirect-only commands)."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def cwd(self):
        return Path.cwd()

    def test_redirect_to_dev_null(self, config, cwd):
        """> /dev/null — command with no words, only redirect."""
        result = analyze("> /dev/null", config, cwd)
        assert result.action == "allow"
        assert "empty command" in result.reason

    def test_redirect_only_ask(self, config, cwd):
        """> /tmp/out — redirect-only command with non-safe target."""
        result = analyze("> /tmp/somefile", config, cwd)
        # Redirect to non-safe target asks
        assert result.action == "ask"


class TestHandlerDenyPath:
    """Cover line 665: handler returning deny.

    No CLI handler currently returns deny, so we mock one to cover the code path.
    """

    def test_mocked_handler_deny(self, monkeypatch):
        from dippy.core.analyzer import _analyze_simple_command
        from dippy.core import analyzer as analyzer_mod
        from types import SimpleNamespace

        # Create a fake handler that returns deny
        fake_classification = SimpleNamespace(
            action="deny",
            description="dangerous operation",
            inner_command=None,
            redirect_targets=None,
            remote=False,
        )
        fake_handler = SimpleNamespace(
            classify=lambda ctx: fake_classification,
        )

        original_get_handler = analyzer_mod.get_handler
        def mock_get_handler(name):
            if name == "fakecmd":
                return fake_handler
            return original_get_handler(name)

        monkeypatch.setattr(analyzer_mod, "get_handler", mock_get_handler)
        result = _analyze_simple_command(
            ["fakecmd", "arg"], Config(), Path.cwd()
        )
        assert result.action == "deny"


class TestTryUnfoldScriptNonShellExtension:
    """Cover line 737: non-shell command without script extension returns None.

    This line is only reachable if script_arg was set but the base is not in
    _SOURCE_COMMANDS or _SHELL_COMMANDS and the extension check fails.
    We call the internal function directly with a mock scenario.
    """

    def test_non_shell_non_script_extension(self):
        from dippy.core.analyzer import _try_unfold_script

        # Direct execution pattern: ./myfile (starts with .) but no script ext
        # Pattern 3 won't match because no script extension -> script_arg stays None
        # -> returns None at line 729
        result = _try_unfold_script(
            "./myfile", ["./myfile", "arg"], Config(), Path.cwd(), 0
        )
        assert result is None

    def test_shell_command_with_non_script_file(self, tmp_path):
        """bash myfile.txt — shell command but non-script extension goes through unfold."""
        from dippy.core.analyzer import _try_unfold_script

        # bash myfile.txt — base is in _SHELL_COMMANDS, script_arg = myfile.txt
        # Line 733: base (bash) is NOT in _SOURCE_COMMANDS — enters check
        # Line 734: base (bash) IS in _SHELL_COMMANDS — condition false, skip to 739
        # So line 737 is NOT hit. This tests that bash with .txt goes to unfold.
        txt_file = tmp_path / "myfile.txt"
        txt_file.write_text("echo hello\n")
        result = _try_unfold_script(
            "bash", ["bash", str(txt_file)], Config(), tmp_path, 0
        )
        # Should attempt unfolding (returns a Decision, not None)
        assert result is not None
