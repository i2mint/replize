"""Tools for make REPL interfaces.

`replize` is a function that converts a command line program into a REPL.

>>> from replize import replize
>>> replize("ls")  # doctest: +SKIP

"""
from replize.replize import replize
