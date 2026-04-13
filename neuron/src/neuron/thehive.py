"""HTTP client for TheHive (neuron image and live tests)."""
from __future__ import annotations

from os import environ
from pathlib import Path
from typing import Any, BinaryIO, Literal, Sequence

from httpx import BasicAuth, Client

AttachmentPart = Path | str | tuple[str, bytes | BinaryIO] | tuple[str, bytes | BinaryIO, str | None]


class ThehiveClient(Client):
    """
    Sync HTTP client for TheHive (``TH_URL``, ``TH_KEY`` or ``TH_USER`` / ``TH_PASSWORD``).

    Subclasses :class:`httpx.Client` so ``base_url``, request methods, and connection lifecycle
    behave like httpx. Adds TheHive-specific construction from env, :meth:`get_observable`,
    :meth:`tag_observable`, :meth:`untag_observable`, and :meth:`add_attachments` for cases and alerts.
    """

    def __init__(
        self,
        base_url: str | None = None,
        key: str | None = None,
        user: str | None = None,
        password: str | None = None,
        *,
        timeout: float = 120.0,
        verify: bool = True,
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

    def tag_observable(self, observable_id: str, tags: Sequence[str]) -> None:
        """
        Add tags to an observable (TheHive 5+ ``PATCH /api/v1/observable/{id}`` with ``addTags``).

        Existing tags are left in place; ``tags`` are merged in. Requires ``manageObservable``.
        """
        if not tags:
            raise ValueError('tags must contain at least one tag')
        r = self.patch(f'/api/v1/observable/{observable_id}', json={'addTags': list(tags)})
        r.raise_for_status()

    def untag_observable(self, observable_id: str, tags: Sequence[str]) -> None:
        """
        Remove tags from an observable (TheHive 5+ ``PATCH /api/v1/observable/{id}`` with ``removeTags``).

        Tags not present on the observable are ignored by the server. Requires ``manageObservable``.
        """
        if not tags:
            raise ValueError('tags must contain at least one tag')
        r = self.patch(f'/api/v1/observable/{observable_id}', json={'removeTags': list(tags)})
        r.raise_for_status()

    def add_attachments(
        self,
        entity_id: str,
        attachments: Sequence[AttachmentPart],
        *,
        type: Literal['case', 'alert'],
        can_rename: bool = False,
    ) -> dict[str, Any]:
        """
        POST multipart ``attachments`` to ``/api/v1/{type}/{entity_id}/attachments`` and return the JSON body.

        ``type`` selects the case or alert route. Path items are opened in binary mode (basename is the
        filename); tuple items are ``(filename, bytes | binary stream)`` or include an optional MIME type
        as a third element. File handles opened from paths are closed after the request; streams supplied
        in tuples are left to the caller.
        """
        if type not in ('alert', 'case'):
            raise ValueError(f'type must be "case" or "alert", got {type!r}')
        if not attachments:
            raise ValueError('attachments must contain at least one file')
        path = f'/api/v1/{type}/{entity_id}/attachments'
        files: list[tuple[str, Any]] = []
        opened: list[BinaryIO] = []
        try:
            for item in attachments:
                if isinstance(item, (str, Path)):
                    file_path = Path(item)
                    fh = file_path.open('rb')
                    opened.append(fh)
                    files.append(('attachments', (file_path.name, fh)))
                elif isinstance(item, tuple):
                    if len(item) == 2:
                        name, payload = item
                        content_type: str | None = None
                    elif len(item) == 3:
                        name, payload, content_type = item
                    else:
                        raise TypeError(f'attachment tuple must have length 2 or 3, got {len(item)}')
                    if isinstance(payload, bytes):
                        files.append(
                            ('attachments', (name, payload, content_type or 'application/octet-stream')),
                        )
                    elif content_type:
                        files.append(('attachments', (name, payload, content_type)))
                    else:
                        files.append(('attachments', (name, payload)))
                else:
                    raise TypeError(f'unsupported attachment item type: {item!r}')
            post_kw: dict[str, Any] = {'files': files}
            if can_rename:
                post_kw['data'] = {'canRename': 'true'}
            r = self.post(path, **post_kw)
            r.raise_for_status()
            return r.json()
        finally:
            for fh in opened:
                fh.close()
