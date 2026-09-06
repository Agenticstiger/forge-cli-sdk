"""Product Guardrail profile — forge-cli-sdk.

Hand-written and deliberately NOT synced: this is where the repo-specific
facts live so that canon_payload.py and check.py can stay byte-identical
across every repo. If scope or grace ever migrates into those, the copies stop
being identical and the drift check stops meaning anything.

This repo is public. Everything in SURFACE_TIER is read by people who have
never seen the product, which is the whole reason the vocabulary has to hold.
"""

# The product ships American spelling. The canon is British, and a rename
# sweep across the products was considered and rejected — the spelling is a
# locale, not an identity. Symmetric: in this repo "Command Centre" is now a
# finding too, so the rule keeps working rather than becoming a no-op.
LOCALE = "en-US"

# Product-facing prose: what a reader of this SDK actually sees.
SURFACE_TIER = (
    "README.md",
    "docs/",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "LICENSE",
    "NOTICE",
    "examples/",
)

EXCLUDED = (
    # A changelog is a record of what was said at the time. Rewriting it to a
    # name adopted after that release is falsification, not compliance.
    "CHANGELOG.md",
    "node_modules",
    "build",
    "dist",
    ".venv",
    "*.egg-info",
    # The guardrail quotes every term it forbids.
    "tools/product_guardrail/",
)

SCAN_ENTITY_FILES = True

# Files that ARE the copy — every string literal is user-facing, not only the
# ones under a copy-shaped keyword. None in this repo yet.
PY_ALL_STRINGS = ()

# Floors. A scan that collapses must fail loudly rather than pass vacuously:
# a checker that silently iterates zero files reports success while proving
# nothing. Set below today's real numbers, not at them, so ordinary growth
# does not trip them.
MIN_FILES_SCANNED = 44
MIN_BYTES_READ = 190_000
MIN_SPANS_EXTRACTED = 295
# The floor that matters: characters actually handed to the rules.
# The other three count containers, and all three can be met by a scan
# that extracted nothing.
MIN_TEXT_EXTRACTED = 59_000

# Known findings: scheduled, owned, printed every run, suppressed from the
# exit code but never from sight. Empty on day one, and meant to stay that way.
GRACE = []
