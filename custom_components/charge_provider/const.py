"""Shared constants for charging-service providers."""

from datetime import timedelta

DOMAIN = "charge_provider"
CONF_PROVIDER = "provider"
PROVIDER_ENBW = "enbw"
POLL_INTERVAL = timedelta(minutes=30)
