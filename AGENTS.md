# AGENTS.md

## Purpose

Cerebro is a FastAPI service that exposes a Cortex-compatible API for TheHive and launches Kubernetes Jobs for analyzers and responders. The repo is used to develop the API server plus a nested neuron worker package; deployment values and production image pins live in adjacent repos, not here.

## Architecture

- `src/cerebro/api.py` builds the FastAPI app, mounts TheHive-compatible routes, internal worker callback routes, and `/metrics`.
- `src/cerebro/routers/thehive.py` is the external Cortex-compatible surface used by TheHive for status, analyzer/responder listing, run requests, job status polling, and waitreport polling.
- `src/cerebro/routers/internal.py` exposes worker callback endpoints used by Kubernetes job pods.
- `src/cerebro/models/base.py` owns worker config loading, TheHive artefact parsing, Kubernetes Job creation/fetching, and worker/job state.
- `src/cerebro/models/cortex.py` wraps base models with Cortex/TheHive response fields.
- `src/cerebro/callback.py` stores only worker callback reports in process memory.
- `neuron/` is a separate Python subproject for the Kubernetes job image; run its commands from `neuron/`.
- `k8s/` contains local/sample Kubernetes deployment inputs. The production Helm chart is in `/Users/plup/platforms/cerebro-deploy`.

## Key Decisions

- Cerebro treats Cortex compatibility as a local API contract. Do not rely on local TheHive source as authoritative for current behavior; the deployed TheHive project is no longer open source and local checkouts can be stale.
- Worker definitions are YAML mappings loaded from `WORKER_CONFIG`, either one file or a directory of `*.yml` / `*.yaml` files. Deployment projects mount one worker per ConfigMap under `/etc/cerebro/workers`.
- Job identity metadata is stored on the Kubernetes Job annotations. While the Job exists, annotations are the source of truth for the original analyzer/responder type.
- If Kubernetes refuses to create a Job, the analyzer/responder run route returns HTTP `503` with a top-level `message` and does not fabricate a job id or write job metadata.
- When Kubernetes reports a Job as `NotFound`, Cerebro returns an HTTP failure instead of inventing an analyzer or responder.

## Configuration & Parametrisation

- `WORKER_CONFIG` points to a worker YAML file or directory; defaults to `/etc/cerebro/workers`.
- `CEREBRO_API_KEY` secures TheHive-compatible routes and worker callbacks unless auth is disabled.
- `CEREBRO_DISABLE_AUTH=1` disables API auth for local/test deployments.
- `CEREBRO_CALLBACK_URL` enables callback env injection for worker pods.
- `OVERRIDE_WORKER_IMAGE` replaces the worker image in launched manifests.
- `TH_URL`, `TH_KEY`, `TH_USER`, and `TH_PASSWORD` are copied into worker pods when present.
- Cerebro needs Kubernetes RBAC for Job and Pod read/create access. Worker definition ConfigMaps are mounted by the deployment chart rather than created by the API process.
- Live tests use `RUN_LIVE_TESTS`, `THEHIVE_LIVE_URL` or `TH_URL`, `THEHIVE_API_KEY` or `TH_KEY`, optional `TH_USER` / `TH_PASSWORD`, and `TH_VERIFY`.

## Code Structure & Patterns

- New TheHive/Cortex endpoints belong in `src/cerebro/routers/thehive.py`; internal worker-only endpoints belong in `src/cerebro/routers/internal.py`.
- Keep core orchestration and Kubernetes behavior in `src/cerebro/models/base.py`; keep response compatibility fields in `src/cerebro/models/cortex.py`.
- Workers are represented by `Worker`; analyzers and responders derive compatibility-specific fields in `Analyzer` and `Responder`.
- Kubernetes failures should return operator-readable `errorMessage` values using `kubernetes_api_exception_detail()`. Branch on Kubernetes `Status.reason`/message where possible, not only numeric HTTP status.
- Job annotations are the durable shape for TheHive-facing job identity while the Kubernetes Job exists. Update the annotation contract when job creation or terminal fetch behavior changes.
- Tests for API routes live in `tests/unit/test_api.py`; model and job-state behavior lives in `tests/unit/test_models.py`.

## Conventions

- Use `uv` for Python commands.
- Run root server tests with `uv run pytest tests`; running bare `uv run pytest` from the root also collects `neuron/tests`, which require the nested package environment.
- Run neuron tests from `neuron/`, for example `cd neuron && uv run python -m unittest discover -s tests`.
- Keep source changes separate from deployment-image pin changes in `/Users/plup/kube/docker-images/cerebro` and Helm/deploy changes in `/Users/plup/platforms/cerebro-deploy`.

## Known Limitations

- `callback.py` is in-memory only. A Cerebro pod restart can still lose callback reports that were not persisted through a terminal fetch.
- A failed waitreport for a missing Kubernetes Job returns `503` rather than a fabricated Cortex job, because returning the wrong analyzer/responder type causes TheHive to keep retrying with misleading errors.
- The full repo contains two Python packages: root `cerebro` and nested `neuron`. Validate them with their own environments unless you are intentionally testing cross-package packaging.
