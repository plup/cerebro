"""HTTP client for TheHive (neuron image and live tests)."""
from __future__ import annotations

from os import environ
from typing import Any

import requests
from urllib.parse import urljoin


class ThehiveClient(requests.Session):
    """HTTP session for TheHive (``TH_URL``, ``TH_KEY`` or ``TH_USER`` / ``TH_PASSWORD``)."""

    def __init__(
        self,
        base_url: str | None = None,
        key: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        super().__init__()
        self.base_url = base_url if base_url is not None else environ['TH_URL']
        if key is None:
            key = environ.get('TH_KEY')
        if user is None:
            user = environ.get('TH_USER')
        if password is None:
            password = environ.get('TH_PASSWORD')
        if key:
            self.headers = {'Authorization': f'Bearer {key}'}
        else:
            self.auth = (user, password)

    def request(self, method, url, *args, **kwargs):
        joined_url = urljoin(self.base_url, url)
        return super().request(method, joined_url, *args, **kwargs)

    def get_observable(self, observable_id: str) -> dict[str, Any]:
        """
        Fetch a single observable by id (TheHive 5+ ``GET /api/v1/observable/{id}``).

        TheHive 4 / v0 deployments often expose case artifacts as
        ``GET /api/v0/case/artifact/{id}`` or alert artifacts as
        ``GET /api/v0/alert/artifact/{id}`` instead; call :meth:`request` with those paths if
        needed.
        """
        r = self.get(f'/api/v1/observable/{observable_id}')
        r.raise_for_status()
        return r.json()
