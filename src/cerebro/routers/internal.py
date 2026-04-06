"""Internal endpoints (worker callbacks), not used by TheHive."""
from os import environ

from fastapi import APIRouter, Depends, Header, HTTPException

from cerebro.callback import store_job_report

router = APIRouter(tags=['internal'])

BEARER_PREFIX = 'Bearer '


def verify_job_callback_token(authorization: str | None = Header(None)) -> None:
    """Require ``Authorization: Bearer`` matching ``CEREBRO_CALLBACK_SECRET``."""
    try:
        expected = environ['CEREBRO_CALLBACK_SECRET']
    except KeyError:
        raise HTTPException(status_code=503, detail='Job callback is not configured')
    if authorization is None:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    if not authorization.startswith(BEARER_PREFIX):
        raise HTTPException(status_code=401, detail='Authorization must be a Bearer token')
    token = authorization[len(BEARER_PREFIX):]
    if token != expected:
        raise HTTPException(status_code=403, detail='Invalid callback token')


@router.post('/api/job/{id}/callback')
def post_job_callback(id: str, body: dict, _: None = Depends(verify_job_callback_token)) -> dict:
    """
    Worker pods POST a Cortex-shaped report here when ``CEREBRO_CALLBACK_SECRET`` is set.

    The JSON body is stored and returned from ``report`` on the job once Kubernetes reports the
    job as Success or Failure (replacing the default log-derived report).
    """
    store_job_report(id, body)
    return {'status': 'Ok'}
