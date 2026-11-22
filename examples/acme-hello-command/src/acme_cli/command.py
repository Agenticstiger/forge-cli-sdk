"""``fluid acme-hello``: print the id of a contract."""

from __future__ import annotations

import argparse
import logging

from fluid_sdk import CommandPlugin, ContractHelper


class HelloCommand(CommandPlugin):
    name = "acme-hello"
    help = "Print a greeting, and the id of a contract when one is given"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--who", default="world", help="whom to greet")
        parser.add_argument("--contract", help="a contract.fluid.yaml (JSON or YAML)")

    def run(self, args: argparse.Namespace, logger: logging.Logger) -> int:
        print(f"hello {args.who}")
        if args.contract:
            import json
            from pathlib import Path

            text = Path(args.contract).read_text(encoding="utf-8")
            try:
                contract = json.loads(text)
            except ValueError:
                import yaml  # forge-cli ships PyYAML; imported only when needed

                contract = yaml.safe_load(text)
            print(f"contract id: {ContractHelper(contract).id}")
        return 0


command = HelloCommand()
