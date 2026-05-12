"""Demo — run steward-validator against three contracts (bad/warn/good).

Usage:

    python demo.py
"""

from __future__ import annotations

from steward_validator.validator import StewardValidator

CONTRACTS = {
    "missing steward": {"id": "p1", "metadata": {"labels": {}}},
    "no steward email": {"id": "p2", "metadata": {"labels": {"principal.steward.id": "emp-12345"}}},
    "fully compliant": {
        "id": "p3",
        "metadata": {
            "labels": {
                "principal.steward.id": "emp-12345",
                "principal.steward.email": "steward@example.com",
            }
        },
    },
}


def main() -> None:
    plugin = StewardValidator()
    for label, contract in CONTRACTS.items():
        print(f"\n=== {label} ===")
        actions = plugin.plan(contract)
        result = plugin.apply(actions)

        if not actions:
            print("  ✓ no findings")
            continue

        for a in actions:
            sev = a["params"]["severity"].upper()
            code = a["params"]["code"]
            msg = a["params"]["message"]
            remediation = a["params"]["remediation"]
            print(f"  [{sev}] {code}: {msg}")
            print(f"          ↳ {remediation}")

        print(f"  → applied={result.applied} failed={result.failed}")


if __name__ == "__main__":
    main()
