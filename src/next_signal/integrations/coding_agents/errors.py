"""Errors with stable, operator-readable coding-agent messages."""


class CodingAgentProtocolError(RuntimeError):
    """Raised when a provider's machine-readable output breaks its contract."""
