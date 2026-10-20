"""Behavioural tests for ``replize``: the REPL loop, its callbacks and the CLI.

Input is scripted by patching ``builtins.input``; output is collected through the
``stdout_callback`` / ``stderr_callback`` seams. Subprocess dispatch is tested against
the running Python interpreter, so no external program is assumed.
"""

import importlib
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

# ``replize.replize`` the *function* shadows the submodule on the package, so get the
# module explicitly.
replize_module = importlib.import_module("replize.replize")
replize = replize_module.replize

#: A command that is the current interpreter running ``-c``; the REPL line is the code.
PY_C = f"{shlex.quote(sys.executable)} -c"


def script_input(monkeypatch, lines):
    """Make ``input`` return ``lines`` in turn, recording the prompts it was given.

    An item that is an exception class or instance is raised instead of returned. Asking
    for more input than scripted fails the test rather than hanging it.
    """
    remaining = list(lines)
    prompts = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        if not remaining:
            raise AssertionError("replize asked for more input than was scripted")
        item = remaining.pop(0)
        if isinstance(item, BaseException) or (
            isinstance(item, type) and issubclass(item, BaseException)
        ):
            raise item
        return item

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def run(command=PY_C, **kwargs):
    """Run the REPL collecting what each callback receives."""
    out, err = [], []
    replize(command, stdout_callback=out.append, stderr_callback=err.append, **kwargs)
    return out, err


def test_runs_a_command_and_hands_stdout_to_the_callback(monkeypatch):
    script_input(monkeypatch, ["\"print('hello')\"", "exit"])
    out, err = run()
    assert [o.decode().strip() for o in out] == ["hello"]
    assert err == []


def test_stdout_and_stderr_go_to_their_own_callbacks(monkeypatch):
    code = "\"import sys; print('to-out'); print('to-err', file=sys.stderr)\""
    script_input(monkeypatch, [code, "exit"])
    out, err = run()
    assert [o.decode().strip() for o in out] == ["to-out"]
    assert [e.decode().strip() for e in err] == ["to-err"]


def test_empty_streams_do_not_call_callbacks(monkeypatch):
    script_input(monkeypatch, ["\"pass\"", "exit"])
    out, err = run()
    assert out == [] and err == []


def test_blank_lines_are_ignored(monkeypatch):
    prompts = script_input(monkeypatch, ["", "   ", "exit"])
    out, err = run()
    assert out == [] and err == []
    assert len(prompts) == 3  # blank lines re-prompt; they never reach a subprocess


def test_each_line_is_a_separate_invocation(monkeypatch):
    script_input(monkeypatch, ["\"print(1)\"", "\"print(2)\"", "exit"])
    out, _ = run()
    assert [o.decode().strip() for o in out] == ["1", "2"]


@pytest.mark.parametrize("exit_word", ["exit", "quit"])
def test_default_exit_commands_end_the_loop(monkeypatch, exit_word):
    # Nothing is scripted after the exit word: reading again would fail the test.
    script_input(monkeypatch, [exit_word])
    assert run() == ([], [])


def test_exit_command_is_the_first_word_only(monkeypatch):
    """``exit now`` exits; the words after the exit command are not run."""
    script_input(monkeypatch, ["exit now"])
    assert run() == ([], [])


def test_exit_word_later_in_a_line_is_an_argument(monkeypatch):
    """Only the first word is checked: a later ``exit`` is passed on to the command."""
    script_input(monkeypatch, ['"import sys; print(sys.argv[1])" exit', "exit"])
    out, _ = run()
    assert [o.decode().strip() for o in out] == ["exit"]


@pytest.mark.parametrize("word", ["exiting", "quitter", "exitx"])
def test_exit_commands_match_whole_words_not_prefixes(monkeypatch, word):
    prompts = script_input(monkeypatch, [f'"print(1)" {word}', f"{word}", "exit"])
    run()
    assert len(prompts) == 3  # neither line ended the loop; only ``exit`` did


def test_custom_exit_commands_replace_the_defaults(monkeypatch):
    script_input(monkeypatch, ["bye"])
    assert run(exit_commands=["bye"]) == ([], [])
    # ``exit`` is no longer special: it is run (``python -c exit`` is a silent no-op) and
    # the loop goes on to read ``bye``.
    prompts = script_input(monkeypatch, ["exit", "bye"])
    assert run(exit_commands=["bye"]) == ([], [])
    assert len(prompts) == 2


@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_default_exit_exceptions_end_the_loop(monkeypatch, exc):
    script_input(monkeypatch, [exc])
    assert run() == ([], [])


def test_custom_exit_exceptions(monkeypatch):
    script_input(monkeypatch, [ValueError])
    assert run(exit_exceptions=[ValueError]) == ([], [])


def test_exception_outside_exit_exceptions_propagates(monkeypatch):
    script_input(monkeypatch, [ValueError("boom")])
    with pytest.raises(ValueError, match="boom"):
        run()


def test_callback_can_end_the_loop_by_raising_an_exit_exception(monkeypatch):
    """The docstring's trick: a callback raising an ``exit_exceptions`` member exits."""
    script_input(monkeypatch, ["\"print('stop')\"", "\"print('never')\""])
    seen = []

    def stop_on_stop(data):
        seen.append(data.decode().strip())
        raise EOFError

    replize(PY_C, stdout_callback=stop_on_stop, stderr_callback=print)
    assert seen == ["stop"]


def test_prompt_is_rendered_from_the_template(monkeypatch):
    prompts = script_input(monkeypatch, ["exit"])
    run("some-tool", prompt_template="[{command}]$ ")
    assert prompts == ["[some-tool]$ "]


def test_prompt_template_is_used_verbatim(monkeypatch):
    prompts = script_input(monkeypatch, ["exit"])
    run("ls", prompt_template="{command}>")
    assert prompts == ["ls>"]


def test_default_prompt(monkeypatch):
    prompts = script_input(monkeypatch, ["exit"])
    run("ls")
    assert prompts == ["ls >>> "]


def test_command_line_is_command_plus_typed_arguments(monkeypatch):
    """Dispatch builds ``shlex.split('<command> <line>')`` and pipes both streams."""
    calls = []

    class FakeProcess:
        def communicate(self):
            return b"fake-out", b""

    def fake_popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return FakeProcess()

    monkeypatch.setattr(replize_module, "Popen", fake_popen)
    script_input(monkeypatch, ["-l 'a b'", "exit"])
    out, _ = run("ls")
    assert out == [b"fake-out"]
    ((argv, kwargs),) = calls
    assert argv == ["ls", "-l", "a b"]
    assert kwargs["stdout"] == kwargs["stderr"] == subprocess.PIPE


def test_default_callbacks_print_decoded_output(monkeypatch, capsys):
    script_input(monkeypatch, ["\"print('plain')\"", "exit"])
    replize(PY_C)
    assert capsys.readouterr().out.strip() == "plain"


def test_decode_and_print(capsys):
    replize_module.decode_and_print("héllo".encode())
    assert capsys.readouterr().out == "héllo\n"


# --------------------------------------------------------------------------------------
# The console script
# --------------------------------------------------------------------------------------


def test_cli_passes_arguments_to_replize(monkeypatch):
    captured = {}
    monkeypatch.setattr(replize_module, "replize", lambda **kw: captured.update(kw))
    monkeypatch.setattr(
        sys,
        "argv",
        ["replize", "git", "--prompt-template", "{command}> ", "--exit-commands", "q", "x"],
    )
    replize_module._replize_cli()
    assert captured == {
        "command": "git",
        "prompt_template": "{command}> ",
        "exit_commands": ["q", "x"],
    }


def test_cli_defaults(monkeypatch):
    captured = {}
    monkeypatch.setattr(replize_module, "replize", lambda **kw: captured.update(kw))
    monkeypatch.setattr(sys, "argv", ["replize", "ls"])
    replize_module._replize_cli()
    assert captured == {
        "command": "ls",
        "prompt_template": "{command} >>> ",
        "exit_commands": ("exit", "quit"),
    }


def test_cli_requires_a_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["replize"])
    with pytest.raises(SystemExit) as info:
        replize_module._replize_cli()
    assert info.value.code == 2
    assert "command" in capsys.readouterr().err


def test_console_script_target_exists():
    """``[project.scripts]`` points at ``replize.replize:_replize_cli``."""
    assert callable(getattr(replize_module, "_replize_cli"))


def test_cli_end_to_end_in_a_real_process(tmp_path):
    """``python -m replize.replize`` run for real: piped stdin, EOF ends the session.

    Run from an empty directory with the package's parent on ``PYTHONPATH``, so the
    result does not depend on the caller's working directory (from inside ``replize/``,
    ``replize.py`` would shadow the package).
    """
    package_parent = Path(replize_module.__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(package_parent)}
    result = subprocess.run(
        [sys.executable, "-m", "replize.replize", PY_C, "--prompt-template", "P> "],
        input="\"print('e2e')\"\n",
        capture_output=True,
        text=True,
        timeout=60,
        cwd=tmp_path,
        env=env,
    )
    assert result.returncode == 0
    assert "e2e" in result.stdout
    assert "P> " in result.stdout


def test_a_command_that_cannot_be_run_is_reported_and_the_repl_goes_on(monkeypatch):
    prompts = script_input(monkeypatch, ["x", "exit"])
    out, err = run("/nonexistent/no_such_program")
    assert out == []
    assert len(err) == 1 and b"no_such_program" in err[0]
    assert len(prompts) == 2  # it prompted again after the failure
