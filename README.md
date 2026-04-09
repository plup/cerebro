# Cerebro

Blueteam automation orchestrator: Cortex-compatible API for TheHive and Kubernetes job execution.

## Repository layout

- **Root `pyproject.toml`** — installable package **`cerebro`** from **`src/cerebro/`** (API server, models, routers). It does **not** include the job container code.
- **`neuron/`** — **nested subproject** in the same shape as Cerebro: its own **`pyproject.toml`**, **`src/`** tree, **`uv.lock`**, and **Hatchling** wheel (`cerebro-neuron`). It exists to build the **Kubernetes neuron/job image** (`neuron/Dockerfile`). Treat it like a sibling mini-repo: run **`uv sync`**, **`uv build`**, or **`uv run`** from **`neuron/`** when working on that image or on `neuron.test`.

## Run in kubernetes

Build the images:
```
$ docker buildx build . -t cerebro -f k8s/cerebro.dock
$ docker build -f neuron/Dockerfile neuron -t worker
```

Deploy Cerebro and TheHive:
```
$ kubectl apply -f k8s/
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
# TH_VERIFY_SSL=0
```

| Variable | Purpose |
|----------|---------|
| `RUN_LIVE_TESTS` | `1` / `true` / `yes` — required or live tests are skipped |
| `THEHIVE_LIVE_URL` | Base URL (preferred) |
| `TH_URL` | Used if `THEHIVE_LIVE_URL` is unset |
| `THEHIVE_API_KEY` or `TH_KEY` | Bearer token |
| `TH_USER` + `TH_PASSWORD` | Basic auth if no API key |
| `TH_VERIFY_SSL` | Set to `0` / `false` / `no` / `off` if HTTPS uses a self-signed cert (local dev). Default is to verify. |

## Create alerts

With a user created in a non admin organisation (set as default):
```
$ curl -X POST -H 'Content-Type: application/json' $THEHIVE/api/v1/alert -u user@thehive.local:secret -d @tests/alert.json
```
