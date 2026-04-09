"""Internal endpoints (worker callbacks), not used by TheHive."""
import secrets
from os import environ

from fastapi import APIRouter, Depends, Header, HTTPException

from cerebro.auth import BEARER_PREFIX
from cerebro.callback import store_job_report

router = APIRouter(tags=['internal'])


def verify_job_callback_token(authorization: str | None = Header(None)) -> None:
    """Require ``Authorization: Bearer`` matching :envvar:`CEREBRO_API_KEY` (same key as TheHive)."""
    try:
        expected = environ['CEREBRO_API_KEY']
    except KeyError:
        raise HTTPException(
            status_code=503,
            detail='Job callback is not configured (set CEREBRO_API_KEY)',
        )
    if authorization is None:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    if not authorization.startswith(BEARER_PREFIX):
        raise HTTPException(status_code=401, detail='Authorization must be a Bearer token')
    token = authorization.removeprefix(BEARER_PREFIX)
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail='Invalid API key')


@router.post('/api/job/{id}/callback')
def post_job_callback(id: str, body: dict, _: None = Depends(verify_job_callback_token)) -> dict:
    """
    Worker pods POST a Cortex-shaped report here when callback env is configured (``CEREBRO_API_KEY``
    and ``CEREBRO_CALLBACK_URL`` on Cerebro; workers receive ``CEREBRO_CALLBACK_TOKEN``).

    The JSON body is stored and returned from ``report`` on the job once Kubernetes reports the
    job as Success or Failure (replacing the default log-derived report).
    """
    store_job_report(id, body)
    return {'status': 'Ok'}
