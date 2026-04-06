"""FastAPI application: Cortex-compatible API for TheHive plus internal worker callbacks."""
import json
import logging

from fastapi import FastAPI
from starlette.requests import Request

from cerebro.routers import internal, thehive

logger = logging.getLogger(__name__)

app = FastAPI(title='cerebro')

app.include_router(thehive.router)
app.include_router(internal.router)


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
