# Cortex API — routes used by TheHive

Base URL: your Cortex instance (e.g. `https://cortex.example.com`). All paths below are relative to that base.

Unless noted, responses are JSON. Successful list/search endpoints return a **JSON array** streamed as the body and include an **`X-Total`** header with the item count.

Authentication matches your Cortex setup (e.g. API key in the `Authorization` header). Role expectations are noted per route.

---

## Status

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/status` | *(none)* | Server version strings (Cortex, Elastic4Play, Play, etc.), auth-related config (`authType`, `capabilities`, `ssoAutoLogin`, `protectDownloadsWith`). |

**Sample `200` body**

```json
{
  "versions": {
    "Cortex": "3.1.0",
    "Elastic4Play": "0.3.0",
    "Play": "2.9.0",
    "Elastic4s": "8.11.5",
    "ElasticSearch client": "7.17.13"
  },
  "config": {
    "protectDownloadsWith": "changeme",
    "authType": "key",
    "capabilities": ["changePassword", "setPassword"],
    "ssoAutoLogin": false
  }
}
```

(`authType` may be a JSON string or an array of strings when multiple providers are configured.)

---

## Alerts

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/alert` | `read` | JSON array of alert names (e.g. `ObsoleteAnalyzers`, `ObsoleteResponders`) when enabled analyzers/responders are outdated. |

**Sample `200` body**

No obsolete workers:

```json
[]
```

With obsolete analyzers:

```json
["ObsoleteAnalyzers"]
```

---

## Analyzers

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/analyzer` | `read` | List analyzers; body parsed as empty/minimal `Fields` (same query model as `_search`). |
| `POST` | `/api/analyzer/_search` | `read` | Search/list analyzers. Body (`application/json`): `query` (optional, elastic4play query), `range` (e.g. pagination), `sort` (string array). |
| `GET` | `/api/analyzer/:id` | `read` | Get one analyzer by id. |
| `GET` | `/api/analyzer/type/:dataType` | `read` | List analyzers whose `dataTypeList` includes `dataType`. |
| `POST` | `/api/analyzer/:id/run` | `analyze` | **Run an analyzer.** Body: `dataType`, and either `data` (string) or `attachment` (file upload); optional `tlp`, `pap`, `message`, `parameters` (object), `label`, `force`. Returns the **job** entity (no embedded report). |

**Sample `200` for `GET /api/analyzer`, `POST /api/analyzer/_search`, `GET /api/analyzer/type/:dataType`**

Body is a **JSON array** of analyzer objects (streamed). Header **`X-Total`**: total count (e.g. `3`). Non–org-admin users get `analyzerDefinitionId` on each item; sensitive `configuration` is omitted.

```json
[
  {
    "workerDefinitionId": "e4f2c8b1a9d3e7f6a2b4c8d0e1f2a3b4",
    "name": "MISP_2",
    "version": "3.0.0",
    "description": "Query MISP for events and attributes",
    "author": "TheHive-Project",
    "url": "https://github.com/TheHive-Project/Cortex-Analyzers",
    "license": "AGPL-V3",
    "dataTypeList": ["domain", "ip", "hash", "url"],
    "baseConfig": "misp",
    "type": "analyzer",
    "createdBy": "user@org",
    "createdAt": 1712419200000,
    "updatedBy": "user@org",
    "updatedAt": 1712419300000,
    "_routing": "org-id",
    "_seqNo": 2,
    "_primaryTerm": 1,
    "id": "a1b2c3d4e5f6789012345678abcdef01",
    "analyzerDefinitionId": "e4f2c8b1a9d3e7f6a2b4c8d0e1f2a3b4"
  }
]
```

**Sample `200` for `GET /api/analyzer/:id`**

Single object, same shape as one element of the array above.

**Sample `200` for `POST /api/analyzer/:id/run`**

New job (no `report` field). Values vary by input and timing (`status` is often `Waiting` or `InProgress` immediately after creation).

```json
{
  "workerDefinitionId": "e4f2c8b1a9d3e7f6a2b4c8d0e1f2a3b4",
  "workerId": "a1b2c3d4e5f6789012345678abcdef01",
  "workerName": "MISP_2",
  "organization": "org-id",
  "status": "Waiting",
  "dataType": "domain",
  "data": "\"evil.example\"",
  "tlp": 2,
  "pap": 2,
  "message": "",
  "parameters": {},
  "type": "analyzer",
  "cacheTag": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "createdBy": "user@org",
  "createdAt": 1712419200000,
  "updatedBy": "user@org",
  "updatedAt": 1712419200000,
  "_routing": "org-id",
  "_seqNo": 0,
  "_primaryTerm": 1,
  "id": "job-uuid-here",
  "input": "evil.example",
  "analyzerId": "a1b2c3d4e5f6789012345678abcdef01",
  "analyzerName": "MISP_2",
  "analyzerDefinitionId": "e4f2c8b1a9d3e7f6a2b4c8d0e1f2a3b4",
  "date": 1712419200000
}
```

---

## Responders

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/responder` | `read` | List responders (same pattern as analyzers). |
| `POST` | `/api/responder/_search` | `read` | Search/list responders; same body shape as `/api/analyzer/_search`. |
| `GET` | `/api/responder/:id` | `read` | Get one responder by id. |
| `GET` | `/api/responder/type/:dataType` | `read` | List responders for `dataType`. |
| `POST` | `/api/responder/:id/run` | `analyze` | **Run a responder.** Same general body idea as analyzer run (`data` normalized to string server-side). Returns the **job** entity. |

**Sample `200` for `GET /api/responder`, `POST /api/responder/_search`, `GET /api/responder/type/:dataType`**

JSON **array** (streamed), header **`X-Total`**. Non–org-admin listing uses worker JSON without extra definition merge; org admins may see `configuration` on some routes.

```json
[
  {
    "workerDefinitionId": "b3c4d5e6f7a80912b3c4d5e6f7a80912",
    "name": "Mailer_1",
    "version": "2.1.0",
    "description": "Send an email notification",
    "author": "TheHive-Project",
    "url": "https://github.com/TheHive-Project/Cortex-Analyzers",
    "license": "AGPL-V3",
    "dataTypeList": ["thehive:case", "thehive:alert"],
    "baseConfig": "smtp",
    "type": "responder",
    "createdBy": "user@org",
    "createdAt": 1710000000000,
    "updatedBy": "user@org",
    "updatedAt": 1710000000000,
    "_routing": "org-id",
    "_seqNo": 1,
    "_primaryTerm": 1,
    "id": "f9e8d7c6b5a4938271605f4e3d2c1b0a"
  }
]
```

**Sample `200` for `GET /api/responder/:id`**

One responder object; when the server enriches from the definition, extra fields such as `maxTlp`, `maxPap`, and definition metadata may appear alongside the worker fields.

**Sample `200` for `POST /api/responder/:id/run`**

Same **job** shape as analyzer run, with `type`: `"responder"` and responder-specific `workerName` / ids.

```json
{
  "workerDefinitionId": "b3c4d5e6f7a80912b3c4d5e6f7a80912",
  "workerId": "f9e8d7c6b5a4938271605f4e3d2c1b0a",
  "workerName": "Mailer_1",
  "organization": "org-id",
  "status": "Waiting",
  "dataType": "thehive:case",
  "tlp": 2,
  "pap": 2,
  "message": "",
  "parameters": {},
  "type": "responder",
  "cacheTag": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
  "createdBy": "user@org",
  "createdAt": 1712419200000,
  "updatedBy": "user@org",
  "updatedAt": 1712419200000,
  "_routing": "org-id",
  "_seqNo": 0,
  "_primaryTerm": 1,
  "id": "job-responder-uuid",
  "input": { "id": "case-id", "customFields": {} },
  "analyzerId": "f9e8d7c6b5a4938271605f4e3d2c1b0a",
  "analyzerName": "Mailer_1",
  "analyzerDefinitionId": "b3c4d5e6f7a80912b3c4d5e6f7a80912",
  "date": 1712419200000
}
```

(`input` is echoed as JSON for responders; `data` may also be present parsed as JSON in the job output per model rules.)

---

## Jobs (reports)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/job/:id/waitreport` | `read` | **Wait for completion**, then return the **job** JSON plus a **`report`** field. Query: `atMost` (duration string, default `1minute`) — max wait before returning current state. |

### `report` shape (after `waitreport`)

- **Success:** object with `success: true`, `summary`, `full`, `operations` (JSON parsed from the worker report), and `artifacts` (array).
- **Failure:** object with `success: false`, `errorMessage`, `input`.
- **Non-terminal / odd states:** `report` may be the string `"Running"`, `"Waiting"`, or `"Deleted"` instead of an object.

**Sample `200` — success**

Job fields plus `report` with parsed analyzer output and artifacts:

```json
{
  "workerDefinitionId": "e4f2c8b1a9d3e7f6a2b4c8d0e1f2a3b4",
  "workerId": "a1b2c3d4e5f6789012345678abcdef01",
  "workerName": "MISP_2",
  "organization": "org-id",
  "status": "Success",
  "dataType": "domain",
  "data": "\"evil.example\"",
  "tlp": 2,
  "pap": 2,
  "message": "",
  "parameters": {},
  "type": "analyzer",
  "startDate": 1712419205000,
  "endDate": 1712419210000,
  "createdBy": "user@org",
  "createdAt": 1712419200000,
  "updatedBy": "user@org",
  "updatedAt": 1712419210000,
  "_routing": "org-id",
  "_seqNo": 5,
  "_primaryTerm": 1,
  "id": "job-uuid-here",
  "input": "evil.example",
  "analyzerId": "a1b2c3d4e5f6789012345678abcdef01",
  "analyzerName": "MISP_2",
  "analyzerDefinitionId": "e4f2c8b1a9d3e7f6a2b4c8d0e1f2a3b4",
  "date": 1712419200000,
  "report": {
    "success": true,
    "summary": {
      "taxonomies": [
        {
          "predicate": "MISP",
          "namespace": "MISP",
          "value": "events:2",
          "level": "info"
        }
      ]
    },
    "full": {
      "results": [
        {
          "type": "domain",
          "value": "evil.example",
          "event_id": "101"
        }
      ]
    },
    "operations": [],
    "artifacts": [
      {
        "data": "192.0.2.10",
        "dataType": "ip",
        "message": null,
        "tags": ["MISP"],
        "tlp": 2
      }
    ]
  }
}
```

**Sample `200` — worker failure**

```json
{
  "id": "job-uuid-here",
  "status": "Failure",
  "workerName": "MISP_2",
  "type": "analyzer",
  "report": {
    "success": false,
    "errorMessage": "Connection refused: /127.0.0.1:10444",
    "input": "\"evil.example\""
  }
}
```

(Other job fields are still present on real responses; the snippet is shortened.)

**Sample `200` — still running after `atMost` elapsed**

`report` is a **string** (not an object):

```json
{
  "id": "job-uuid-here",
  "status": "InProgress",
  "type": "analyzer",
  "report": "Running"
}
```

---

## Typical TheHive flow

1. `GET /api/status` — connectivity and version.
2. `GET /api/alert` — optional warnings.
3. List or resolve analyzers: `GET`/`POST /api/analyzer` or `GET /api/analyzer/type/:dataType`.
4. `POST /api/analyzer/:id/run` — obtain `job.id`.
5. `GET /api/job/:id/waitreport` — poll/wait for the full result with `report`.

Same pattern for responders using the `/api/responder/...` and `/api/responder/:id/run` routes.
