"""acme-chat-alerts — an alert route kind and an organisation's default route."""

from acme_alerts.defaults import default_routes
from acme_alerts.forge import ChatNotifier

__all__ = ["ChatNotifier", "default_routes"]
