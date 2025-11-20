"""Tests for replize core functionality."""

import pytest
import sys
from io import StringIO
from unittest.mock import patch, MagicMock, call
from replize.replize import replize, decode_and_print, _replize_cli


class TestDecodeAndPrint:
    """Tests for decode_and_print function."""

    def test_decode_and_print_basic(self, capsys):
        """Test basic decoding and printing."""
        test_bytes = b"Hello, World!"
        decode_and_print(test_bytes)
        captured = capsys.readouterr()
        assert captured.out == "Hello, World!\n"

    def test_decode_and_print_multiline(self, capsys):
        """Test decoding multiline output."""
        test_bytes = b"Line 1\nLine 2\nLine 3"
        decode_and_print(test_bytes)
        captured = capsys.readouterr()
        assert captured.out == "Line 1\nLine 2\nLine 3\n"


class TestReplize:
    """Tests for replize function."""

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_basic_command_execution(self, mock_input, mock_popen):
        """Test basic command execution in REPL."""
        # Setup mock
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_popen.return_value = mock_process

        # Simulate: run "ls -l" then exit
        mock_input.side_effect = ["arg1", "exit"]

        with patch('replize.replize.decode_and_print') as mock_print:
            replize("echo")

            # Verify command was executed
            assert mock_popen.called
            assert mock_print.call_count == 1

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_quit_command(self, mock_input, mock_popen):
        """Test that 'quit' exits the REPL."""
        mock_input.side_effect = ["quit"]

        replize("echo")

        # Should exit without running command
        assert not mock_popen.called

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_custom_exit_commands(self, mock_input, mock_popen):
        """Test custom exit commands."""
        mock_input.side_effect = ["bye"]

        replize("echo", exit_commands=["bye", "stop"])

        assert not mock_popen.called

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_eof_error_exits(self, mock_input, mock_popen):
        """Test that EOFError exits the REPL."""
        mock_input.side_effect = EOFError()

        # Should not raise, just exit
        replize("echo")

        assert not mock_popen.called

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_keyboard_interrupt_exits(self, mock_input, mock_popen):
        """Test that KeyboardInterrupt exits the REPL."""
        mock_input.side_effect = KeyboardInterrupt()

        # Should not raise, just exit
        replize("echo")

        assert not mock_popen.called

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_custom_exit_exceptions(self, mock_input, mock_popen):
        """Test custom exit exceptions."""
        class CustomExit(Exception):
            pass

        mock_input.side_effect = CustomExit()

        # Should exit gracefully
        replize("echo", exit_exceptions=(CustomExit,))

        assert not mock_popen.called

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_empty_input_ignored(self, mock_input, mock_popen):
        """Test that empty input is ignored."""
        mock_input.side_effect = ["", "  ", "\t", "exit"]

        replize("echo")

        # Should not execute command for empty inputs
        assert not mock_popen.called

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_stdout_callback(self, mock_input, mock_popen):
        """Test custom stdout callback."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"stdout output", b"")
        mock_popen.return_value = mock_process

        mock_input.side_effect = ["arg", "exit"]
        mock_callback = MagicMock()

        replize("echo", stdout_callback=mock_callback)

        mock_callback.assert_called_once_with(b"stdout output")

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_stderr_callback(self, mock_input, mock_popen):
        """Test custom stderr callback."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"stderr output")
        mock_popen.return_value = mock_process

        mock_input.side_effect = ["arg", "exit"]
        mock_callback = MagicMock()

        replize("echo", stderr_callback=mock_callback)

        mock_callback.assert_called_once_with(b"stderr output")

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_both_stdout_and_stderr(self, mock_input, mock_popen):
        """Test both stdout and stderr in same execution."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"out", b"err")
        mock_popen.return_value = mock_process

        mock_input.side_effect = ["arg", "exit"]
        mock_stdout_cb = MagicMock()
        mock_stderr_cb = MagicMock()

        replize("echo", stdout_callback=mock_stdout_cb, stderr_callback=mock_stderr_cb)

        mock_stdout_cb.assert_called_once_with(b"out")
        mock_stderr_cb.assert_called_once_with(b"err")

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_custom_prompt_template(self, mock_input, mock_popen):
        """Test custom prompt template."""
        mock_input.side_effect = ["exit"]

        with patch('builtins.input', side_effect=["exit"]) as mock_input:
            replize("git", prompt_template="{command} $ ")

            # Check that input was called with formatted prompt
            mock_input.assert_called_with("git $ ")

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_command_with_arguments(self, mock_input, mock_popen):
        """Test that commands are properly combined with arguments."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_popen.return_value = mock_process

        mock_input.side_effect = ["-l -a", "exit"]

        with patch('replize.replize.decode_and_print'):
            replize("ls")

            # Verify the full command was split correctly
            call_args = mock_popen.call_args
            assert call_args[0][0] == ['ls', '-l', '-a']

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_multiple_commands(self, mock_input, mock_popen):
        """Test executing multiple commands before exit."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"out", b"")
        mock_popen.return_value = mock_process

        mock_input.side_effect = ["arg1", "arg2", "arg3", "exit"]

        with patch('replize.replize.decode_and_print'):
            replize("echo")

            # Should have been called 3 times
            assert mock_popen.call_count == 3

    @patch('replize.replize.Popen')
    @patch('builtins.input')
    def test_no_output_no_callback(self, mock_input, mock_popen):
        """Test that callbacks aren't called when there's no output."""
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_popen.return_value = mock_process

        mock_input.side_effect = ["arg", "exit"]
        mock_callback = MagicMock()

        replize("echo", stdout_callback=mock_callback, stderr_callback=mock_callback)

        # Callback should not be called for empty output
        mock_callback.assert_not_called()


class TestReplizeCLI:
    """Tests for _replize_cli function."""

    @patch('replize.replize.replize')
    @patch('sys.argv', ['replize', 'ls'])
    def test_basic_cli_invocation(self, mock_replize):
        """Test basic CLI invocation."""
        _replize_cli()

        mock_replize.assert_called_once()
        call_args = mock_replize.call_args
        assert call_args[1]['command'] == 'ls'

    @patch('replize.replize.replize')
    @patch('sys.argv', ['replize', 'git', '--prompt-template', 'git> '])
    def test_cli_with_custom_prompt(self, mock_replize):
        """Test CLI with custom prompt template."""
        _replize_cli()

        call_args = mock_replize.call_args
        assert call_args[1]['command'] == 'git'
        assert call_args[1]['prompt_template'] == 'git> '

    @patch('replize.replize.replize')
    @patch('sys.argv', ['replize', 'docker', '--exit-commands', 'q', 'bye'])
    def test_cli_with_custom_exit_commands(self, mock_replize):
        """Test CLI with custom exit commands."""
        _replize_cli()

        call_args = mock_replize.call_args
        assert call_args[1]['command'] == 'docker'
        assert call_args[1]['exit_commands'] == ['q', 'bye']

    @patch('sys.argv', ['replize'])
    def test_cli_no_command_fails(self):
        """Test that CLI fails without a command."""
        with pytest.raises(SystemExit):
            _replize_cli()
