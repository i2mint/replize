# replize.replize

### replize.replize(command, \*, prompt_template='{command} >>> ', exit_commands=('exit', 'quit'), exit_exceptions=(<class 'EOFError'>, <class 'KeyboardInterrupt'>), stdout_callback=<function decode_and_print>, stderr_callback=<function decode_and_print>)

Converts a command line into a REPL.

Usage:

```bash
$ replize <command>
```

### Example

```bash
$ replize ls
ls >>> -l
total 8
-rw-r--r-- 1 user group  0 Jan  1 00:00 __init__.py
-rw-r--r-- 1 user group  0 Jan  1 00:00 __main__.py
-rw-r--r-- 1 user group  0 Jan  1 00:00 __pycache__
-rw-r--r-- 1 user group  0 Jan  1 00:00 replize.py
ls >>> exit
$
```

Tricks:

`replize` is meant to be used with `functools.partial` to make the kind of REPL
factory YOU want, by changing the defaults.

If you want a given stdout or stderr value to have the effect of exiting the REPL,
you can set the callback to raise an exception that is in the `exit_exceptions`.
