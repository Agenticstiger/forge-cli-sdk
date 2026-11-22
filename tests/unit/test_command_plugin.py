"""The CommandPlugin role."""

from __future__ import annotations

import argparse
import logging

import pytest

from fluid_sdk import CommandPlugin
from fluid_sdk.testing import CommandPluginTestHarness


class Hello(CommandPlugin):
    name = "hello"
    help = "Say hello"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--who", default="world")

    def run(self, args: argparse.Namespace, logger: logging.Logger) -> int:
        print(f"hello {args.who}")
        return 0


command = Hello()


class TestHello(CommandPluginTestHarness):
    command_entry_point = command
    expected_commands = ("hello",)
    reserved_command_names = ("init", "validate", "plan", "apply")


def test_register_adds_one_parser_with_func_and_cmd() -> None:
    root = argparse.ArgumentParser()
    sp = root.add_subparsers(dest="cmd")
    command(sp)
    args = root.parse_args(["hello", "--who", "x"])
    assert args.cmd == "hello" and args.who == "x"
    assert args.func(args, logging.getLogger("t")) == 0


def test_a_command_needs_a_name() -> None:
    class Nameless(CommandPlugin):
        pass

    sp = argparse.ArgumentParser().add_subparsers()
    with pytest.raises(ValueError, match="name"):
        Nameless().register(sp)


def test_run_is_abstract() -> None:
    with pytest.raises(NotImplementedError):
        CommandPlugin().run(argparse.Namespace(), logging.getLogger("t"))
