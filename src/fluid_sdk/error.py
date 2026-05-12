"""Error types used throughout the FLUID SDK.

Distinguishing user-actionable errors from internal bugs is critical so the
FLUID CLI can render appropriate messages and decide whether to surface
stack traces.
"""

from __future__ import annotations


class PluginError(RuntimeError):
    """A plugin-detected error caused by user input, contract content, or
    environment misconfiguration.

    The CLI surfaces the message verbatim and may attach context but does
    NOT print a stack trace by default — the message is the actionable
    payload.
    """


class PluginInternalError(RuntimeError):
    """An internal bug or unexpected environmental failure inside a plugin.

    The CLI prints the message AND a stack trace because the user cannot
    fix this without filing an issue.
    """


__all__ = ["PluginError", "PluginInternalError"]
