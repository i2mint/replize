"""REPLize a command line program."""

from collections.abc import Iterable, Callable
from subprocess import Popen, PIPE
from shlex import split as shlex_split
from typing import Optional, Any
import sys
import os
import shutil
from pathlib import Path

# Optional dependencies - graceful degradation
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.completion import PathCompleter
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    PromptSession = None

try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich import print as rich_print
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python
    except ImportError:
        tomllib = None

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def decode_and_print(x: bytes) -> None:
    """Decode bytes and print to stdout.

    Args:
        x: Bytes to decode and print
    """
    print(x.decode())


class ReplizeConfig:
    """Configuration for a replize session."""

    def __init__(
        self,
        command: str,
        prompt_template: str = '{command} >>> ',
        exit_commands: Iterable[str] = ('exit', 'quit'),
        exit_exceptions: Iterable[type[Exception]] = (EOFError, KeyboardInterrupt),
        stdout_callback: Optional[Callable[[bytes], Any]] = None,
        stderr_callback: Optional[Callable[[bytes], Any]] = None,
        use_rich: bool = True,
        use_prompt_toolkit: bool = True,
        history_file: Optional[str] = None,
        enable_history: bool = True,
        enable_completion: bool = True,
        enable_syntax_highlighting: bool = True,
        timeout: Optional[float] = None,
        log_file: Optional[str] = None,
        pre_command_hooks: Optional[list[Callable]] = None,
        post_command_hooks: Optional[list[Callable]] = None,
        verbose_exit: bool = False,
        show_return_code: bool = False,
        validate_command: bool = True,
    ):
        """Initialize replize configuration.

        Args:
            command: The base command to replize
            prompt_template: Template for prompt string (supports {command})
            exit_commands: Commands that will exit the REPL
            exit_exceptions: Exceptions that will exit the REPL
            stdout_callback: Callback for stdout (default: decode_and_print)
            stderr_callback: Callback for stderr (default: decode_and_print)
            use_rich: Use rich library for enhanced output (if available)
            use_prompt_toolkit: Use prompt_toolkit for enhanced input (if available)
            history_file: Path to history file (default: ~/.replize_history)
            enable_history: Enable command history
            enable_completion: Enable tab completion
            enable_syntax_highlighting: Enable syntax highlighting
            timeout: Timeout for subprocess execution in seconds
            log_file: Path to log file for session recording
            pre_command_hooks: Hooks to run before command execution
            post_command_hooks: Hooks to run after command execution
            verbose_exit: Print exit message when exiting
            show_return_code: Show return code after each command
            validate_command: Validate that base command exists before starting
        """
        self.command = command
        self.prompt_template = prompt_template
        self.exit_commands = set(exit_commands)
        self.exit_exceptions = tuple(exit_exceptions)
        self.stdout_callback = stdout_callback or decode_and_print
        self.stderr_callback = stderr_callback or decode_and_print
        self.use_rich = use_rich and HAS_RICH
        self.use_prompt_toolkit = use_prompt_toolkit and HAS_PROMPT_TOOLKIT
        self.history_file = history_file
        self.enable_history = enable_history
        self.enable_completion = enable_completion
        self.enable_syntax_highlighting = enable_syntax_highlighting
        self.timeout = timeout
        self.log_file = log_file
        self.pre_command_hooks = pre_command_hooks or []
        self.post_command_hooks = post_command_hooks or []
        self.verbose_exit = verbose_exit
        self.show_return_code = show_return_code
        self.validate_command = validate_command

        # Initialize console for rich output
        self.console = Console() if self.use_rich else None

        # Command counter for dynamic prompts
        self.command_counter = 0

        # Session history for built-in commands
        self.session_history: list[str] = []

    def get_prompt(self) -> str:
        """Get the current prompt string with dynamic substitution.

        Returns:
            Formatted prompt string
        """
        return self.prompt_template.format(
            command=self.command,
            count=self.command_counter,
        )


def validate_base_command(command: str) -> bool:
    """Validate that a command exists in PATH.

    Args:
        command: Command to validate

    Returns:
        True if command exists, False otherwise
    """
    base_cmd = command.split()[0] if ' ' in command else command
    return shutil.which(base_cmd) is not None


def load_config_file(config_path: Optional[str] = None) -> dict:
    """Load configuration from a TOML or YAML file.

    Args:
        config_path: Path to config file (or None to use default)

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        # Try default locations
        default_paths = [
            Path.home() / '.replizerc',
            Path.home() / '.replize.toml',
            Path.home() / '.config' / 'replize' / 'config.toml',
            Path.home() / '.replize.yaml',
            Path.home() / '.config' / 'replize' / 'config.yaml',
        ]

        for path in default_paths:
            if path.exists():
                config_path = str(path)
                break
        else:
            return {}

    config_path = Path(config_path)
    if not config_path.exists():
        return {}

    # Load based on extension
    if config_path.suffix in ['.toml']:
        if tomllib is None:
            print(f"Warning: TOML support not available, skipping {config_path}", file=sys.stderr)
            return {}
        with open(config_path, 'rb') as f:
            return tomllib.load(f)
    elif config_path.suffix in ['.yaml', '.yml']:
        if not HAS_YAML:
            print(f"Warning: YAML support not available, skipping {config_path}", file=sys.stderr)
            return {}
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    else:
        print(f"Warning: Unknown config file format: {config_path}", file=sys.stderr)
        return {}


def replize(
    command: str,
    *,
    prompt_template: str = '{command} >>> ',
    exit_commands: Iterable[str] = ('exit', 'quit'),
    exit_exceptions: Iterable[type[Exception]] = (EOFError, KeyboardInterrupt),
    stdout_callback: Optional[Callable[[bytes], Any]] = None,
    stderr_callback: Optional[Callable[[bytes], Any]] = None,
    **kwargs,
) -> None:
    """Converts a command line into a REPL.

    Usage:

    .. code-block:: bash

        $ replize <command>

    Example:

    .. code-block:: bash

        $ replize ls
        ls >>> -l
        total 8
        -rw-r--r-- 1 user group  0 Jan  1 00:00 __init__.py
        -rw-r--r-- 1 user group  0 Jan  1 00:00 __main__.py
        -rw-r--r-- 1 user group  0 Jan  1 00:00 __pycache__
        -rw-r--r-- 1 user group  0 Jan  1 00:00 replize.py
        ls >>> exit
        $

    Tricks:

    `replize` is meant to be used with `functools.partial` to make the kind of REPL
    factory YOU want, by changing the defaults.

    If you want a given stdout or stderr value to have the effect of exiting the REPL,
    you can set the callback to raise an exception that is in the ``exit_exceptions``.

    Args:
        command: The base command to replize
        prompt_template: Template for prompt string (supports {command}, {count})
        exit_commands: Commands that will exit the REPL
        exit_exceptions: Exceptions that will exit the REPL
        stdout_callback: Callback for stdout (default: decode_and_print)
        stderr_callback: Callback for stderr (default: decode_and_print)
        **kwargs: Additional configuration options (see ReplizeConfig)
    """
    # Create configuration
    config = ReplizeConfig(
        command=command,
        prompt_template=prompt_template,
        exit_commands=exit_commands,
        exit_exceptions=exit_exceptions,
        stdout_callback=stdout_callback,
        stderr_callback=stderr_callback,
        **kwargs,
    )

    # Validate command if requested
    if config.validate_command and not validate_base_command(command):
        if config.console:
            config.console.print(f"[bold red]Error:[/bold red] Command '{command}' not found in PATH", style="red")
        else:
            print(f"Error: Command '{command}' not found in PATH", file=sys.stderr)
        return

    # Setup history
    if config.use_prompt_toolkit and config.enable_history:
        if config.history_file:
            history = FileHistory(os.path.expanduser(config.history_file))
        else:
            history_path = Path.home() / '.replize_history'
            history = FileHistory(str(history_path))
    else:
        history = InMemoryHistory() if config.use_prompt_toolkit else None

    # Setup prompt session
    if config.use_prompt_toolkit:
        completer = PathCompleter() if config.enable_completion else None
        auto_suggest = AutoSuggestFromHistory() if config.enable_history else None
        session = PromptSession(
            history=history,
            completer=completer,
            auto_suggest=auto_suggest,
        )
    else:
        session = None

    # Open log file if requested
    log_file_handle = None
    if config.log_file:
        log_file_handle = open(config.log_file, 'a')
        log_file_handle.write(f"\n=== New replize session: {command} ===\n")

    try:
        _run_repl_loop(config, session, log_file_handle)
    finally:
        if log_file_handle:
            log_file_handle.close()

        if config.verbose_exit:
            if config.console:
                config.console.print("[bold green]Exiting replize[/bold green]")
            else:
                print("Exiting replize")


def _handle_builtin_command(config: ReplizeConfig, arguments_str: str) -> bool:
    """Handle built-in REPL commands.

    Args:
        config: Replize configuration
        arguments_str: User input string

    Returns:
        True if command was handled, False otherwise
    """
    parts = arguments_str.split()
    if not parts:
        return False

    cmd = parts[0]

    # Help command
    if cmd in ('help', '?'):
        _print_help(config)
        return True

    # History command
    if cmd == 'history':
        _print_history(config)
        return True

    # Clear command
    if cmd == 'clear':
        os.system('clear' if os.name != 'nt' else 'cls')
        return True

    # Re-run command from history
    if cmd.startswith('!') and len(cmd) > 1:
        try:
            index = int(cmd[1:])
            if 0 <= index < len(config.session_history):
                return False  # Let it be re-executed
        except ValueError:
            if config.console:
                config.console.print(f"[red]Invalid history reference: {cmd}[/red]")
            else:
                print(f"Invalid history reference: {cmd}", file=sys.stderr)
            return True

    return False


def _print_help(config: ReplizeConfig) -> None:
    """Print help message for built-in commands."""
    help_text = """
Built-in commands:
  help, ?          Show this help message
  history          Show command history
  clear            Clear the screen
  !<n>             Re-run command number <n> from history
  exit, quit       Exit the REPL
"""

    if config.console:
        config.console.print(help_text, style="cyan")
    else:
        print(help_text)


def _print_history(config: ReplizeConfig) -> None:
    """Print command history."""
    if not config.session_history:
        msg = "No command history"
        if config.console:
            config.console.print(msg, style="yellow")
        else:
            print(msg)
        return

    if config.console:
        config.console.print("[bold]Command History:[/bold]")
        for i, cmd in enumerate(config.session_history):
            config.console.print(f"  [cyan]{i}[/cyan]: {cmd}")
    else:
        print("Command History:")
        for i, cmd in enumerate(config.session_history):
            print(f"  {i}: {cmd}")


def _run_repl_loop(
    config: ReplizeConfig,
    session: Optional[Any],
    log_file_handle: Optional[Any],
) -> None:
    """Run the main REPL loop.

    Args:
        config: Replize configuration
        session: Prompt toolkit session (or None)
        log_file_handle: Open log file handle (or None)
    """
    while True:
        try:
            # Get input
            prompt_str = config.get_prompt()

            if session:
                arguments_str = session.prompt(prompt_str).strip()
            else:
                arguments_str = input(prompt_str).strip()

            if not arguments_str:
                continue

            # Log input
            if log_file_handle:
                log_file_handle.write(f"{prompt_str}{arguments_str}\n")
                log_file_handle.flush()

            # Check for exit commands
            first_word, *_ = arguments_str.split() if arguments_str.split() else ['']
            if first_word in config.exit_commands:
                break

            # Handle built-in commands
            if _handle_builtin_command(config, arguments_str):
                continue

            # Handle history reference
            if arguments_str.startswith('!') and len(arguments_str) > 1:
                try:
                    index = int(arguments_str[1:])
                    if 0 <= index < len(config.session_history):
                        arguments_str = config.session_history[index]
                        if config.console:
                            config.console.print(f"[dim]Re-running: {arguments_str}[/dim]")
                        else:
                            print(f"Re-running: {arguments_str}")
                    else:
                        if config.console:
                            config.console.print(f"[red]History index out of range: {index}[/red]")
                        else:
                            print(f"History index out of range: {index}", file=sys.stderr)
                        continue
                except ValueError:
                    pass  # Not a history reference, treat as normal command

            # Add to session history
            config.session_history.append(arguments_str)

            # Run pre-command hooks
            for hook in config.pre_command_hooks:
                try:
                    hook(config.command, arguments_str)
                except Exception as e:
                    if config.console:
                        config.console.print(f"[red]Pre-command hook error: {e}[/red]")
                    else:
                        print(f"Pre-command hook error: {e}", file=sys.stderr)

            # Execute command
            full_command = f'{config.command} {arguments_str}'

            try:
                process = Popen(
                    shlex_split(full_command),
                    stdout=PIPE,
                    stderr=PIPE,
                )

                # Wait for command with optional timeout
                try:
                    stdout, stderr = process.communicate(timeout=config.timeout)
                except TimeoutError:
                    process.kill()
                    stdout, stderr = process.communicate()
                    if config.console:
                        config.console.print(f"[bold red]Command timed out after {config.timeout}s[/bold red]")
                    else:
                        print(f"Command timed out after {config.timeout}s", file=sys.stderr)

                # Handle output
                if stdout:
                    config.stdout_callback(stdout)
                    if log_file_handle:
                        log_file_handle.write(stdout.decode())

                if stderr:
                    config.stderr_callback(stderr)
                    if log_file_handle:
                        log_file_handle.write(stderr.decode())

                # Show return code if requested
                if config.show_return_code and process.returncode != 0:
                    msg = f"Return code: {process.returncode}"
                    if config.console:
                        config.console.print(f"[yellow]{msg}[/yellow]")
                    else:
                        print(msg, file=sys.stderr)

                # Run post-command hooks
                for hook in config.post_command_hooks:
                    try:
                        hook(config.command, arguments_str, process.returncode, stdout, stderr)
                    except Exception as e:
                        if config.console:
                            config.console.print(f"[red]Post-command hook error: {e}[/red]")
                        else:
                            print(f"Post-command hook error: {e}", file=sys.stderr)

            except FileNotFoundError:
                if config.console:
                    config.console.print(f"[bold red]Command not found: {full_command}[/bold red]")
                else:
                    print(f"Command not found: {full_command}", file=sys.stderr)
            except Exception as e:
                if config.console:
                    config.console.print(f"[bold red]Error executing command: {e}[/bold red]")
                else:
                    print(f"Error executing command: {e}", file=sys.stderr)

            # Increment counter
            config.command_counter += 1

        except config.exit_exceptions:
            break


def _replize_cli() -> None:
    """Script to enter a REPL for a command line program given by name"""
    from argparse import ArgumentParser, RawTextHelpFormatter

    parser = ArgumentParser(
        description="Convert any command-line program into an interactive REPL",
        formatter_class=RawTextHelpFormatter,
        epilog="""
Examples:
  replize ls                              # Create a REPL for ls
  replize git --prompt-template "git> "  # Custom prompt
  replize docker --exit-commands q bye   # Custom exit commands

Built-in REPL commands:
  help, ?      Show help
  history      Show command history
  clear        Clear screen
  !<n>         Re-run command <n>
  exit, quit   Exit the REPL
        """
    )

    parser.add_argument('command', help='The command to run.')

    # Give access to prompt_template
    parser.add_argument(
        '--prompt-template',
        default='{command} >>> ',
        help='The template for the prompt (supports {command}, {count}).',
    )

    # Give access to exit_commands
    parser.add_argument(
        '--exit-commands',
        nargs='+',
        default=('exit', 'quit'),
        help='The commands that will exit the REPL.',
    )

    # Optional features
    parser.add_argument(
        '--no-rich',
        action='store_true',
        help='Disable rich output (even if available).',
    )

    parser.add_argument(
        '--no-prompt-toolkit',
        action='store_true',
        help='Disable prompt_toolkit (even if available).',
    )

    parser.add_argument(
        '--history-file',
        help='Path to history file.',
    )

    parser.add_argument(
        '--log-file',
        help='Path to log file for session recording.',
    )

    parser.add_argument(
        '--timeout',
        type=float,
        help='Timeout for command execution in seconds.',
    )

    parser.add_argument(
        '--show-return-code',
        action='store_true',
        help='Show return code after each command.',
    )

    parser.add_argument(
        '--no-validate',
        action='store_true',
        help="Don't validate that the command exists before starting.",
    )

    parser.add_argument(
        '--config',
        help='Path to configuration file (TOML or YAML).',
    )

    args = parser.parse_args()

    # Load config file if specified
    config_dict = load_config_file(args.config) if args.config else {}

    # Command-specific config
    cmd_config = config_dict.get('commands', {}).get(args.command, {})
    defaults = config_dict.get('defaults', {})

    # Merge configs (CLI args > command config > defaults > hardcoded defaults)
    kwargs = {}

    # Apply defaults
    for key, value in defaults.items():
        kwargs[key] = value

    # Apply command-specific config
    for key, value in cmd_config.items():
        kwargs[key] = value

    # Apply CLI arguments (highest priority)
    kwargs['prompt_template'] = args.prompt_template
    kwargs['exit_commands'] = args.exit_commands

    if args.no_rich:
        kwargs['use_rich'] = False

    if args.no_prompt_toolkit:
        kwargs['use_prompt_toolkit'] = False

    if args.history_file:
        kwargs['history_file'] = args.history_file

    if args.log_file:
        kwargs['log_file'] = args.log_file

    if args.timeout:
        kwargs['timeout'] = args.timeout

    if args.show_return_code:
        kwargs['show_return_code'] = True

    if args.no_validate:
        kwargs['validate_command'] = False

    replize(command=args.command, **kwargs)


if __name__ == '__main__':
    _replize_cli()
