"""Live tests: authenticated HTTP to TheHive."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

_neuron_src = Path(__file__).resolve().parents[2] / 'neuron' / 'src'
if str(_neuron_src) not in sys.path:
    sys.path.insert(0, str(_neuron_src))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        'markers',
        'live: needs RUN_LIVE_TESTS=1 and TheHive reachable (see README.md)',
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _live_tests_enabled():
        return
    skip = pytest.mark.skip(reason='Set RUN_LIVE_TESTS=1 to run live tests (see README.md)')
    for item in items:
        if item.get_closest_marker('live'):
            item.add_marker(skip)


def _live_tests_enabled() -> bool:
    return os.environ.get('RUN_LIVE_TESTS', '').lower() in ('1', 'true', 'yes')


@pytest.fixture
def live_thehive_client() -> Generator[Any, None, None]:
    """``neuron.thehive.ThehiveClient`` — same session shape as the neuron image."""
    from neuron.thehive import ThehiveClient

    base = os.environ.get('THEHIVE_LIVE_URL') or os.environ.get('TH_URL')
    if not base:
        pytest.skip(
            'THEHIVE_LIVE_URL or TH_URL must be set (e.g. http://127.0.0.1:9000 after port-forward)'
        )

    key = os.environ.get('THEHIVE_API_KEY') or os.environ.get('TH_KEY')
    user = os.environ.get('TH_USER')
    password = os.environ.get('TH_PASSWORD')

    verify = bool(int(os.environ.get('TH_VERIFY', '1')))
    if key:
        client = ThehiveClient(base_url=base, key=key, verify=verify)
    elif user and password:
        client = ThehiveClient(base_url=base, user=user, password=password, verify=verify)
    else:
        pytest.skip(
            'TheHive auth: set THEHIVE_API_KEY or TH_KEY (Bearer), or TH_USER + TH_PASSWORD'
        )

    try:
        yield client
    finally:
        client.close()
