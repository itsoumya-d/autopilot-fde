"""Ingestion module."""
from .slack_connector import SlackConfigurationError, sync_channel

__all__ = ["SlackConfigurationError", "sync_channel"]
