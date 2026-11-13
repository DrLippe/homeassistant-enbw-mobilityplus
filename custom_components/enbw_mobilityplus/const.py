"""Constants for EnBW mobility+."""

from datetime import timedelta

DOMAIN = "enbw_mobilityplus"
POLL_INTERVAL = timedelta(hours=1)
LIVE_POLL_INTERVAL = timedelta(minutes=5)
ACTIVE_POLL_INTERVAL = timedelta(seconds=30)
