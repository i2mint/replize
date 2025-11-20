# replize

Tools to create REPL interfaces from command-line programs.

Convert any CLI command into an interactive REPL with history, tab completion, and rich features!

## Installation

Basic installation (no optional dependencies):
```bash
pip install replize
```

With all optional features:
```bash
pip install replize[full]
```

Or install specific feature sets:
```bash
pip install replize[prompt_toolkit]  # Enhanced input with history & completion
pip install replize[rich]            # Colorized output
pip install replize[config]          # Configuration file support
```

## Quick Start

```bash
$ replize ls
ls >>> -l
total 8
-rw-r--r-- 1 user group  0 Jan  1 00:00 __init__.py
-rw-r--r-- 1 user group  0 Jan  1 00:00 replize.py
ls >>> -la
total 16
drwxr-xr-x 2 user group 4096 Jan  1 00:00 .
drwxr-xr-x 3 user group 4096 Jan  1 00:00 ..
-rw-r--r-- 1 user group    0 Jan  1 00:00 __init__.py
-rw-r--r-- 1 user group    0 Jan  1 00:00 replize.py
ls >>> exit
$
```

## Features

### Core Features (No Dependencies)

- **Zero Dependencies**: Works out of the box with Python standard library
- **Any Command**: Turn any CLI program into a REPL
- **Exit Commands**: Type `exit` or `quit` to leave the REPL
- **Built-in Commands**: `help`, `history`, `clear`, `!<n>` for re-running commands
- **Customizable**: Use `functools.partial` to create your own REPL factory
- **Command Validation**: Validates command exists before starting
- **Better Error Handling**: Graceful handling of missing commands and errors

### Enhanced Features (Optional Dependencies)

#### 🎨 Rich Output (`pip install replize[rich]`)

- Colorized prompts and error messages
- Syntax-highlighted output
- Beautiful formatting with [rich](https://github.com/Textualize/rich)

#### ⌨️  Enhanced Input (`pip install replize[prompt_toolkit]`)

- **Command History**: Navigate with up/down arrows
- **Persistent History**: Saved across sessions in `~/.replize_history`
- **Tab Completion**: File and path completion
- **Auto-suggestions**: Suggestions from history as you type
- Powered by [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)

#### ⚙️ Configuration Files (`pip install replize[config]`)

- TOML or YAML configuration files
- Per-command customization
- Default locations: `~/.replize.toml`, `~/.config/replize/config.toml`

#### 🔧 Advanced Features

- **Session Logging**: Record entire session to file
- **Command Timeouts**: Prevent hanging commands
- **Return Codes**: Optionally show command exit codes
- **Hook System**: Pre/post-command hooks for customization
- **Dynamic Prompts**: Use `{command}` and `{count}` in prompt templates

## Usage Examples

### Basic Usage

```bash
# Create a git REPL
replize git

# Create a docker REPL with custom prompt
replize docker --prompt-template "🐳 {command} >>> "

# Custom exit commands
replize kubectl --exit-commands q bye stop
```

### Advanced Options

```bash
# Show return codes
replize python --show-return-code

# Set command timeout (30 seconds)
replize npm --timeout 30

# Log session to file
replize git --log-file ~/git-session.log

# Custom history file
replize psql --history-file ~/.psql_replize_history

# Disable optional features
replize ls --no-rich --no-prompt-toolkit
```

### Built-in REPL Commands

Once inside a REPL, you have access to these built-in commands:

- `help` or `?` - Show help message
- `history` - Display command history
- `clear` - Clear the screen
- `!<n>` - Re-run command number n from history
- `exit` or `quit` - Exit the REPL

Example:
```bash
$ replize echo
echo >>> hello
hello
echo >>> world
world
echo >>> history
Command History:
  0: hello
  1: world
echo >>> !0
Re-running: hello
hello
echo >>> exit
```

### Using in Python Code

```python
from replize import replize

# Basic usage
replize("ls")

# With customization
replize(
    "git",
    prompt_template="git 🌿 >>> ",
    exit_commands=["exit", "quit", "q"],
    show_return_code=True,
)

# With hooks
def log_command(command, args):
    print(f"Running: {command} {args}")

def handle_result(command, args, returncode, stdout, stderr):
    if returncode != 0:
        print(f"Warning: Command failed with code {returncode}")

replize(
    "docker",
    pre_command_hooks=[log_command],
    post_command_hooks=[handle_result],
)

# With custom callbacks
def custom_stdout_handler(output: bytes):
    # Custom processing of stdout
    text = output.decode()
    print(f"Output: {text}")

replize("ls", stdout_callback=custom_stdout_handler)
```

### Configuration File

Create a file at `~/.replize.toml`:

```toml
[defaults]
use_rich = true
use_prompt_toolkit = true
enable_history = true
show_return_code = false

[commands.git]
prompt_template = "git 🌿 >>> "
exit_commands = ["exit", "quit", "q"]

[commands.docker]
prompt_template = "🐳 {command} >>> "
show_return_code = true
timeout = 30.0
```

Then use it:

```bash
replize git  # Uses settings from [commands.git]
replize docker  # Uses settings from [commands.docker]
```

You can also specify a custom config file:

```bash
replize git --config ~/my-replize-config.toml
```

### Dynamic Prompts

Use template variables in your prompt:

```bash
# Show command name
replize ls --prompt-template "{command} $ "
# Output: ls $

# Show command counter
replize git --prompt-template "[{count}] {command} >>> "
# Output: [0] git >>>
#         [1] git >>>
#         [2] git >>>
```

## Advanced Usage

### Creating a Custom REPL Factory

Use `functools.partial` to create specialized REPLs:

```python
from functools import partial
from replize import replize

# Create a git REPL factory
git_repl = partial(
    replize,
    command="git",
    prompt_template="git 🌿 >>> ",
    exit_commands=["exit", "quit", "q"],
    enable_history=True,
    show_return_code=True,
)

# Use it
git_repl()
```

### Hook System

Hooks allow you to customize behavior before and after command execution:

```python
# Pre-command hook: runs before each command
def validate_branch(command, args):
    if args.startswith("push") and "--force" in args:
        response = input("Force push detected. Are you sure? (y/n) ")
        if response.lower() != 'y':
            raise KeyboardInterrupt()  # Cancel the command

# Post-command hook: runs after each command
def notify_on_failure(command, args, returncode, stdout, stderr):
    if returncode != 0:
        print(f"🚨 Command failed with exit code {returncode}")
        # Could send notification, log to file, etc.

replize(
    "git",
    pre_command_hooks=[validate_branch],
    post_command_hooks=[notify_on_failure],
)
```

### Session Logging

Record all commands and output:

```python
replize("git", log_file="~/git-session-2024.log")
```

The log file will contain:
```
=== New replize session: git ===
git >>> status
On branch main
Your branch is up to date with 'origin/main'.
...
```

## API Reference

### Main Function

```python
def replize(
    command: str,
    *,
    prompt_template: str = '{command} >>> ',
    exit_commands: Iterable[str] = ('exit', 'quit'),
    exit_exceptions: Iterable[type[Exception]] = (EOFError, KeyboardInterrupt),
    stdout_callback: Optional[Callable[[bytes], Any]] = None,
    stderr_callback: Optional[Callable[[bytes], Any]] = None,
    # Optional features
    use_rich: bool = True,
    use_prompt_toolkit: bool = True,
    history_file: Optional[str] = None,
    enable_history: bool = True,
    enable_completion: bool = True,
    timeout: Optional[float] = None,
    log_file: Optional[str] = None,
    pre_command_hooks: Optional[list[Callable]] = None,
    post_command_hooks: Optional[list[Callable]] = None,
    verbose_exit: bool = False,
    show_return_code: bool = False,
    validate_command: bool = True,
) -> None:
```

**Parameters:**

- `command`: The base command to replize
- `prompt_template`: Template for prompt string (supports `{command}`, `{count}`)
- `exit_commands`: Commands that will exit the REPL
- `exit_exceptions`: Exceptions that will exit the REPL
- `stdout_callback`: Callback function for stdout (default: decode and print)
- `stderr_callback`: Callback function for stderr (default: decode and print)
- `use_rich`: Use rich library for enhanced output (if available)
- `use_prompt_toolkit`: Use prompt_toolkit for enhanced input (if available)
- `history_file`: Path to history file (default: `~/.replize_history`)
- `enable_history`: Enable command history
- `enable_completion`: Enable tab completion
- `timeout`: Timeout for subprocess execution in seconds
- `log_file`: Path to log file for session recording
- `pre_command_hooks`: List of functions to run before command execution
- `post_command_hooks`: List of functions to run after command execution
- `verbose_exit`: Print exit message when exiting
- `show_return_code`: Show return code after each command
- `validate_command`: Validate that base command exists before starting

## Requirements

- Python 3.10+
- No required dependencies!

Optional dependencies:
- `prompt_toolkit>=3.0.0` - For enhanced input features
- `rich>=10.0.0` - For colorized output
- `tomli>=1.2.0` (Python <3.11) or `pyyaml>=5.0.0` - For config file support

## Development

Install with development dependencies:

```bash
pip install -e .[dev]
```

Run tests:

```bash
pytest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Apache License 2.0

## Credits

Developed by [i2mint](https://github.com/i2mint)

## See Also

- [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) - Library for building powerful interactive command lines
- [rich](https://github.com/Textualize/rich) - Rich text and beautiful formatting in the terminal
- [click-repl](https://github.com/click-contrib/click-repl) - REPL plugin for Click
