"""HTTP client for TheHive (neuron image and live tests)."""
from __future__ import annotations

from os import environ
from typing import Any

from httpx import BasicAuth, Client


class ThehiveClient(Client):
    """
    Sync HTTP client for TheHive (``TH_URL``, ``TH_KEY`` or ``TH_USER`` / ``TH_PASSWORD``).

    Subclasses :class:`httpx.Client` so ``base_url``, request methods, and connection lifecycle
    behave like httpx. Only adds TheHive-specific construction from env and :meth:`get_observable`.
    """

    def __init__(
        self,
        base_url: str | None = None,
        key: str | None = None,
        user: str | None = None,
        password: str | None = None,
        *,
        timeout: float = 120.0,
        verify: bool | str = True,
        **kwargs: Any,
    ):
        base = base_url if base_url is not None else environ['TH_URL']
        if key is None:
            key = environ.get('TH_KEY')
        if user is None:
            user = environ.get('TH_USER')
        if password is None:
            password = environ.get('TH_PASSWORD')

        headers: dict[str, str] = {}
        auth: BasicAuth | None = None
        if key:
            headers['Authorization'] = f'Bearer {key}'
        else:
            auth = BasicAuth(user or '', password or '')

        super().__init__(
            base_url=base,
            headers=headers,
            auth=auth,
            timeout=timeout,
            verify=verify,
            **kwargs,
        )

    def get_observable(self, observable_id: str) -> dict[str, Any]:
        """
        Fetch a single observable by id (TheHive 5+ ``GET /api/v1/observable/{id}``).

        TheHive 4 / v0 deployments often expose case artifacts as
        ``GET /api/v0/case/artifact/{id}`` or alert artifacts as
        ``GET /api/v0/alert/artifact/{id}`` instead; use :meth:`get` with those paths if needed.
        """
        r = self.get(f'/api/v1/observable/{observable_id}')
        r.raise_for_status()
        return r.json()
