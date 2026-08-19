"""Ingestion module."""
from .pipeline import IngestionPipeline
from .slack_connector import SlackConfigurationError, sync_channel

__all__ = ["IngestionPipeline", "SlackConfigurationError", "sync_channel"]
