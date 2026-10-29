"""Ingestion module."""
from .feed_parser import FeedItem, FeedParseError, parse_feed
from .slack_connector import SlackConfigurationError, sync_channel

__all__ = ["FeedItem", "FeedParseError", "parse_feed", "SlackConfigurationError", "sync_channel"]
