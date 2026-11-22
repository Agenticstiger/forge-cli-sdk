from __future__ import annotations

import argparse
import json
import logging

from acme_cli.command import command

from fluid_sdk.testing import CommandPluginTestHarness


class TestHelloCommand(CommandPluginTestHarness):
    command_entry_point = command
    expected_commands = ("acme-hello",)
    reserved_command_names = ("init", "validate", "plan", "apply", "generate", "plugins")


def test_runs(tmp_path, capsys) -> None:
    contract = tmp_path / "c.json"
    contract.write_text(json.dumps({"id": "p1"}))
    root = argparse.ArgumentParser()
    command(root.add_subparsers(dest="cmd"))
    args = root.parse_args(["acme-hello", "--who", "me", "--contract", str(contract)])
    assert args.func(args, logging.getLogger("t")) == 0
    assert capsys.readouterr().out == "hello me\ncontract id: p1\n"
