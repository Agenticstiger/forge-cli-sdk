"""Demo — run the hello-scaffold plugin against a fluid contract and see the output.

Usage:

    python demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hello_scaffold.scaffold import HelloScaffold

CONTRACT = {
    "fluidVersion": "0.7.4",
    "kind": "DataProduct",
    "id": "my-first-product",
    "name": "My First Product",
    "description": "A demo product produced by the hello-scaffold plugin.",
    "metadata": {"owner": {"team": "demo", "email": "demo@example.com"}},
}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        plugin = HelloScaffold(output_root=Path(tmp))
        actions = plugin.plan(CONTRACT)
        result = plugin.apply(actions)

        print(f"✓ {result.applied} files written, {result.failed} failed\n")
        for p in sorted(Path(tmp).rglob("*")):
            if p.is_file():
                rel = p.relative_to(tmp)
                print(f"--- {rel} ---")
                print(p.read_text())


if __name__ == "__main__":
    main()
