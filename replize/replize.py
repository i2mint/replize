"""REPLize a command line program."""

from collections.abc import Iterable
from subprocess import Popen, PIPE
from shlex import split as shlex_split


def decode_and_print(x):
    print(x.decode())


def replize(
    command: str,
    *,
    prompt_template: str = '{command} >>> ',
    exit_commands: Iterable[str] = ('exit', 'quit'),
    exit_exceptions: Iterable[Exception] = (EOFError, KeyboardInterrupt),
    stdout_callback=decode_and_print,
    stderr_callback=decode_and_print,
):
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

    """

    exit_commands = set(exit_commands)
    exit_exceptions = tuple(exit_exceptions)

    # TODO: Like this for now, but could make prompt string dynamic in the future
    prompt_str = prompt_template.format(command=command)

    while True:
        try:
            arguments_str = input(prompt_str).strip()
            if arguments_str:
                first_word, *_ = arguments_str.split()
                if first_word in exit_commands:
                    break  # TODO: Enable verbose exit?
                full_command = f'{command} {arguments_str}'
                process = Popen(shlex_split(full_command), stdout=PIPE, stderr=PIPE,)
                stdout, stderr = process.communicate()

                if stdout:
                    stdout_callback(stdout)
                if stderr:
                    stderr_callback(stderr)
        except exit_exceptions:  # TODO: Pylance says this is an error. It's not.
            break  # TODO: Enable verbose exit?


def _replize_cli():
    """Script to enter a REPL for a command line program given by name"""
    from argparse import ArgumentParser, RawTextHelpFormatter

    # TODO: Would like to use replize.__doc__ here, but doesn't format well.
    parser = ArgumentParser(
        description=replize.__doc__, formatter_class=RawTextHelpFormatter
    )

    parser.add_argument('command', help='The command to run.')
    # Give access to prompt_template
    parser.add_argument(
        '--prompt-template',
        default='{command} >>> ',
        help='The template for the prompt.',
    )
    # Give access to exit_commands
    parser.add_argument(
        '--exit-commands',
        nargs='+',
        default=('exit', 'quit'),
        help='The commands that will exit the REPL.',
    )
    args = parser.parse_args()

    replize(
        command=args.command,
        prompt_template=args.prompt_template,
        exit_commands=args.exit_commands,
    )


if __name__ == '__main__':
    _replize_cli()
