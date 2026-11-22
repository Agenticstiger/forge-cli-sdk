"""The :class:`CommandPlugin` role: an extra ``fluid <name>`` subcommand.

A package adds subcommands to the FLUID CLI through the ``fluid_build.commands`` entry-point
group, which forge-cli has read since 0.8.3rc1 and 0.8.3. The entry point loads to a callable that
takes the CLI's argparse ``subparsers`` object and adds its parsers::

    [project.entry-points."fluid_build.commands"]
    acme = "acme_cli.command:command"

From forge-cli 0.11.0 on, the entry-point name is read from metadata and the module is imported
only when the invoked command is not one of forge-cli's own, so ``fluid --help`` and every core
command import nothing from the plugin; the operator's allow/block policy applies to the name;
and ``func`` may take one argument. Earlier versions imported every command plugin while building
the parser. Each parser the callable adds should carry a ``func`` default: forge-cli calls
``func(args, logger)`` (``func(args)`` when ``func`` has fewer than two positional parameters and
no ``*args``) and the return value becomes the exit code.

Because forge-cli calls ``entry_point.load()(subparsers)``, the loaded object must be the
callable itself: a function, or an *instance* of :class:`CommandPlugin`, which is callable.
Do not register the class, which forge-cli would call with the subparsers as its argument.

Example::

    from fluid_sdk import CommandPlugin

    class HelloCommand(CommandPlugin):
        name = "hello"
        help = "Say hello"

        def configure(self, parser):
            parser.add_argument("--who", default="world")

        def run(self, args, logger):
            print(f"hello {args.who}")
            return 0

    command = HelloCommand()   # the entry point names this instance

The role has no ``plan`` / ``apply``, so it does not subclass
:class:`fluid_sdk.base.BasePlugin`.
"""

from __future__ import annotations

import argparse
import logging
from typing import Any

#: Entry-point group of CLI subcommands.
COMMANDS_GROUP = "fluid_build.commands"


class CommandPlugin:
    """Base class of a ``fluid <name>`` subcommand: the typed surface of
    ``fluid_build.commands``.

    Subclass it, set :attr:`name` and :attr:`help`, override :meth:`configure` to add arguments
    and :meth:`run` to do the work, then name an *instance* in the entry point. Registering adds
    one parser and nothing else: no output, no environment change, no imports beyond the
    module's own.
    """

    #: Canonical role tag (not read by forge-cli; used by tooling and the harness).
    role = "command"

    #: The subcommand's name: ``fluid <name>``.
    name: str = ""

    #: The one-line help ``fluid --help`` shows.
    help: str = ""

    def configure(self, parser: argparse.ArgumentParser) -> None:
        """Add the subcommand's arguments to ``parser``."""

    def run(self, args: argparse.Namespace, logger: logging.Logger) -> int:
        """Run the subcommand; the return value is the exit code."""
        raise NotImplementedError(f"{type(self).__name__}.run")

    def register(self, subparsers: Any) -> None:
        """Add this subcommand to the CLI's ``subparsers`` (what forge-cli's loader calls)."""
        if not self.name:
            raise ValueError(f"{type(self).__name__}.name must name the subcommand")
        parser = subparsers.add_parser(self.name, help=self.help or None)
        self.configure(parser)
        parser.set_defaults(cmd=self.name, func=self.run)

    def __call__(self, subparsers: Any) -> None:
        self.register(subparsers)


__all__ = ["COMMANDS_GROUP", "CommandPlugin"]
