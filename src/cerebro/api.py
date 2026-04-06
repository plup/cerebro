"""This module contains all endpoints normally handled by Cortex and a webhook for TheHive."""
import json
import logging
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from importlib.metadata import version
from cerebro.models.cortex import Analyzer, Responder, CortexJob
from cerebro.models.base import ThehiveArtefact, WorkerNotFoundError

logger = logging.getLogger(__name__)
audit = logging.getLogger('audit')
app = FastAPI(title='cerebro')

@app.middleware("http")
async def log_request_body(request: Request, call_next):
    """Log JSON request bodies at DEBUG (Starlette caches body after first read)."""
    if body := await request.body():
        try:
            text = json.loads(body.decode("utf-8"))
            logger.debug(f"{request.method} {request.url.path} body: {text}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return await call_next(request)

## Status polling

@app.get("/api/status")
def status():
    return {"versions": {"Cortex": version('cerebro')}}

@app.get("/api/user/current")
def current_user():
    return {"status":"Ok", "id":"thehive"}

@app.get("/api/alert")
def get_alert():
    return []

## Analyzers

@app.get('/api/analyzer')
def get_analyzers() -> list[Analyzer]:
    """Return the list of available analyzers."""
    return Analyzer.listall()

@app.get('/api/analyzer/{id}')
def get_analyzer(id: str) -> Analyzer:
    """Return the configuration of the analyzer."""
    try:
        return Analyzer.get(id)
    except WorkerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post('/api/analyzer/{id}/run')
def run_analyzer(id: str, event: dict) -> CortexJob:
    """
    Create a new job and wrap it into a Cortex compatible type.

    TheHive sends a flat Cortex analyzer body (observable ``dataType`` and ``data`` string).
    """
    try:
        user = event['parameters']['user']
        artefact = ThehiveArtefact.from_analyzer_event(event)
        audit.info(f"{user} triggered analyzer {id} on {artefact.type} id {artefact.id}")

    except KeyError as e:
        raise HTTPException(status_code=400, detail=f'Missing {e}')

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CortexJob.create(worker_id=id, artefact=artefact)

## Responders

@app.post("/api/responder/_search")
def get_responders() -> list[Responder]:
    """Return the list of available responders."""
    return Responder.listall()

@app.get('/api/responder/{id}')
def get_responder(id: str) -> Responder:
    """Return the configuration of the responder."""
    # seems to be sending the name instead of the id
    try:
        return Responder.get(id)

    except WorkerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post('/api/responder/{id}/run')
def run_responder(id: str, event: dict) -> CortexJob:
    """
    Create a new job and wrap it into a Cortex compatible type.

    It extracts all the required parameters and pass them to the job.

    The responder takes a nested dictionary as input.
    """
    try:
        user = event['parameters']['user']
        artefact = ThehiveArtefact.from_responder_event(event)
        audit.info(f"{user} triggered responder {id} on {artefact.type} id {artefact.id}")

    except KeyError as e:
        raise HTTPException(status_code=400, detail=f'Missing {e}')

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CortexJob.create(worker_id=id, artefact=artefact)

## Jobs

@app.post('/api/job/status')
def get_jobs_status(job_ids: dict) -> dict:
    """Return the status for the jobs."""
    status = {}
    for _id in job_ids['jobIds']:
        status[_id] = CortexJob.fetch(_id).status
    logger.debug(f'Status returned: {status}')
    return status

@app.get('/api/job/{id}/waitreport')
def get_job_report(id: str) -> CortexJob:
    """Return the CortexJob including a report."""
    job = CortexJob.fetch(id)
    logger.debug(f'Job returned: {job.model_dump()}')
    return job
