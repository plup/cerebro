"""This module contains all endpoints normally handled by Cortex and a webhook for TheHive."""
import logging
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from importlib.metadata import version
from cerebro.models.cortex import Analyzer, Responder, CortexJob
from cerebro.models.base import WorkerNotFoundError

app = FastAPI(title='cerebro')
logger = logging.getLogger(__name__)
audit = logging.getLogger('audit')

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
    return [] # disable analysers from current implementation

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
    logger.debug(f'Event received from TheHive: {event}')
    # extract worker parameters
    try:
        kwargs = {
            'worker_id': id,
        }

        # extract observable parameters
        if event['dataType'] == 'thehive:case_artifact':
            kwargs['object_type'] = event['data']['dataType']
            kwargs['object_id'] = event['data']['id']
            try:
                kwargs['context_id'] = event['data']['alert']['id']
                kwargs['context_type'] = 'alert'

            except KeyError:
                kwargs['context_id'] = event['data']['case']['id']
                kwargs['context_type'] = 'case'

        # extract alert parameters
        if event['dataType'] == 'thehive:alert':
            kwargs['object_type'] = 'alert'
            kwargs['object_id'] = event['data']['id']

        # extract case parameters
        if event['dataType'] == 'thehive:case':
            kwargs['object_type'] = 'case'
            kwargs['object_id'] = event['data']['id']

    except KeyError as e:
        raise HTTPException(status_code=400, detail=f'Missing {e}')

    user = event['parameters']['user']
    audit.info(f"{user} triggered responder {id} on {kwargs['object_type']} id {kwargs['object_id']}")

    return CortexJob.create(**kwargs)

## Jobs

@app.post('/api/job/status')
def get_jobs_status(job_ids: dict) -> dict:
    """Return the status for the jobs."""
    status = {}
    for _id in job_ids['jobIds']:
        status[_id] = CortexJob.fetch(_id).status
    return status

@app.get('/api/job/{id}/waitreport')
def get_job_report(id: str) -> CortexJob:
    """Return the CortexJob including a report."""
    logger.debug(f'Result returned by Cerebro: {CortexJob.fetch(id)}')
    return CortexJob.fetch(id)
