# replize

Tools to create REPL interfaces.

To install:	```pip install replize```


# Example usage

## `replize` system command

Converts a command line into a REPL.

Usage:

    $ replize <command>

Example:

    $ replize ls
    ls >>> -l
    total 8
    -rw-r--r-- 1 user group  0 Jan  1 00:00 __init__.py
    -rw-r--r-- 1 user group  0 Jan  1 00:00 __main__.py
    -rw-r--r-- 1 user group  0 Jan  1 00:00 __pycache__
    -rw-r--r-- 1 user group  0 Jan  1 00:00 replize.py
    ls >>> exit
    $

### Recipes

`replize` is meant to be used with `functools.partial` to make the kind of REPL
factory YOU want, by changing the defaults.

If you want a given stdout or stderr value to have the effect of exiting the REPL,
you can set the callback to raise an exception that is in the ``exit_exceptions``.