# Cerebro

Automation orchestrator with a Cortex-compatible API for TheHive and Kubernetes job execution.

## Repository layout

- **Root `pyproject.toml`** — installable package **`cerebro`** from **`src/cerebro/`** (API server, models, routers). It does **not** include the job container code.
- **`neuron/`** — **nested subproject** in the same shape as Cerebro: its own **`pyproject.toml`**, **`src/`** tree, **`uv.lock`**, and **Hatchling** wheel (`cerebro-neuron`). It exists to build the **Kubernetes neuron/job image** (`neuron/Dockerfile`). Treat it like a sibling mini-repo: run **`uv sync`**, **`uv build`**, or **`uv run`** from **`neuron/`** when working on that image or on `neuron.test`.

## Development

Use Skaffold when changing the Cerebro API or the bundled neuron worker code:

```bash
cp skaffold.yaml.sample skaffold.yaml
skaffold run
skaffold delete
```

Keep `skaffold.yaml` local. The tracked sample and `k8s/values-test.yaml` use placeholder image and chart references that can be adapted to your registry.

The Skaffold test values set `CEREBRO_DISABLE_AUTH=1` on the Cerebro server so local-only
API testing does not need TheHive/Cortex credentials. This disables Bearer authentication for
both TheHive-compatible routes and worker callbacks.

Run unit tests:

```bash
uv run --extra dev pytest tests/unit
(cd neuron && uv run python -m unittest discover -s tests)
```

## Build images manually

Build the images:
```
$ docker buildx build . -t cerebro -f k8s/Dockerfile
$ docker build -f neuron/Dockerfile neuron -t worker
```

Access TheHive:
```
$ kubectl get svc/thehive
NAME      TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)
thehive   NodePort   10.43.112.109   <none>        9000:30001/TCP

$ export THEHIVE=http://localhost:30001
```

## Live tests (TheHive)

Tests under **`tests/live/`** call a **real TheHive** over HTTP. They are **off by default** unless **`RUN_LIVE_TESTS`** is set (see table).

Put the variables you need in a **`.env`** file at the repo root (do not commit it; it may hold secrets), then run:

```bash
uv run --env-file=.env pytest tests/live -m live -v
```

Example **`.env`** (use either API key **or** basic auth):

```bash
RUN_LIVE_TESTS=1
THEHIVE_LIVE_URL=http://127.0.0.1:9000
THEHIVE_API_KEY=your-key-here
# or: TH_URL=...  TH_KEY=...
# or: TH_USER=user@thehive.local  TH_PASSWORD=secret
# HTTPS with a self-signed cert (e.g. port-forward to TLS in the cluster):
# TH_VERIFY=0
```

| Variable | Purpose |
|----------|---------|
| `RUN_LIVE_TESTS` | `1` / `true` / `yes` — required or live tests are skipped |
| `THEHIVE_LIVE_URL` | Base URL (preferred) |
| `TH_URL` | Used if `THEHIVE_LIVE_URL` is unset |
| `THEHIVE_API_KEY` or `TH_KEY` | Bearer token |
| `TH_USER` + `TH_PASSWORD` | Basic auth if no API key |
| `TH_VERIFY` | Read by neuron and live tests: `0` disables TLS verification; default `1`. The client accepts ``verify: bool = True``. |

## Metrics

Cerebro exposes Prometheus text metrics on `/metrics`.

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `cerebro_job_runs_total` | counter | `worker`, `invocation_type` | Jobs observed by Cerebro since process start. |
| `cerebro_jobs` | gauge | `worker`, `invocation_type`, `status` | Jobs grouped by their latest observed worker status (`in_progress`, `success`, `failure`). |

## Create alerts

With a user created in a non admin organisation (set as default):
```
$ curl -X POST -H 'Content-Type: application/json' $THEHIVE/api/v1/alert -u user@thehive.local:secret -d @tests/alert.json
```
