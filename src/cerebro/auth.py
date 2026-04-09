"""Shared HTTP Bearer helpers for Cerebro."""
from __future__ import annotations

import secrets
from os import environ

from fastapi import Header, HTTPException

BEARER_PREFIX = 'Bearer '


def verify_api_key(authorization: str | None = Header(None)) -> None:
    """
    Require ``Authorization: Bearer`` matching :envvar:`CEREBRO_API_KEY` (Cortex-compatible API key).

    Used for routes TheHive calls as a Cortex client. When the variable is unset, returns 503.
    """
    try:
        expected = environ['CEREBRO_API_KEY']
    except KeyError:
        raise HTTPException(
            status_code=503,
            detail='API authentication is not configured (set CEREBRO_API_KEY)',
        )
    if authorization is None:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    if not authorization.startswith(BEARER_PREFIX):
        raise HTTPException(status_code=401, detail='Authorization must be a Bearer token')
    token = authorization.removeprefix(BEARER_PREFIX)
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail='Invalid API key')
