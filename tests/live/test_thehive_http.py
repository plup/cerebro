"""Scenarios: HTTP calls to a running TheHive instance."""

import pytest


@pytest.mark.live
def test_thehive_user_current(live_thehive_client):
    """Authenticated session works against TheHive API (v1 ``user/current``)."""
    r = live_thehive_client.get('/api/v1/user/current')
    r.raise_for_status()
    body = r.json()
    assert isinstance(body, dict)
