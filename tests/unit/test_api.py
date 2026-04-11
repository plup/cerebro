"""Module testing the fastapi response validation."""
from fastapi.testclient import TestClient
from kubernetes.client.exceptions import ApiException
from kubernetes.utils.create_from_yaml import FailToCreateError

from cerebro.api import app
from cerebro.models.base import JobExecutionError
from cerebro.models.cortex import *

_CORTEX_AUTH_HEADERS = {'Authorization': 'Bearer test-cortex-key'}
client = TestClient(app, headers=_CORTEX_AUTH_HEADERS)

def test_polling():
    """Simulate TheHive status checking."""
    r = client.get('/api/status')
    assert r.json()['versions']
    r = client.get('/api/user/current')
    assert r.json()['status'] == 'Ok'
    r = client.get('/api/alert')
    assert r.status_code == 200

def test_list_analyzer(default_workers):
    r = client.get('/api/analyzer')
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]['name'] == 'bar'
    assert data[0]['type'] == 'analyzer'


def test_get_analyzer(default_workers):
    r = client.get('/api/analyzer/bar')
    assert r.status_code == 200
    assert r.json()['name'] == 'bar'

def test_list_responder(default_workers):
    r = client.post('/api/responder/_search')
    assert r.status_code == 200

def test_get_responder(default_workers):
    r = client.get('/api/responder/foo')
    assert r.status_code == 200

def test_get_nothing():
    r = client.get('/api/analyzer/nothing')
    assert r.status_code == 404


def test_thehive_routes_require_bearer(monkeypatch):
    monkeypatch.setenv('CEREBRO_API_KEY', 'secret-key')
    unauth = TestClient(app)
    assert unauth.get('/api/status').status_code == 401


def test_thehive_rejects_wrong_bearer(monkeypatch):
    monkeypatch.setenv('CEREBRO_API_KEY', 'secret-key')
    bad = TestClient(app, headers={'Authorization': 'Bearer wrong'})
    assert bad.get('/api/status').status_code == 403


def test_job_callback_stores_report(monkeypatch):
    monkeypatch.setenv('CEREBRO_API_KEY', 'test-secret')
    r = client.post(
        '/api/job/my-job-id/callback',
        json={'success': True, 'full': {'message': 'ok'}},
        headers={'Authorization': 'Bearer test-secret'},
    )
    assert r.status_code == 200
    from cerebro.callback import get_job_report

    assert get_job_report('my-job-id') == {'success': True, 'full': {'message': 'ok'}}


def test_job_callback_rejects_bad_token(monkeypatch):
    monkeypatch.setenv('CEREBRO_API_KEY', 'test-secret')
    r = client.post(
        '/api/job/my-job-id/callback',
        json={'success': True},
        headers={'Authorization': 'Bearer wrong'},
    )
    assert r.status_code == 403


def test_run_analyzer_kubernetes_admission_denied(default_workers, mocker):
    """Kyverno / admission failures return a finished job with error in ``report`` (HTTP 200)."""
    mocker.patch('cerebro.models.base.K8sJob.load_kube_config', return_value='default')
    api_ex = ApiException(status=400, reason='Bad Request')
    api_ex.body = (
        '{"kind":"Status","status":"Failure","message":"policy: images must use SHA256","code":400}'
    )
    mocker.patch(
        'cerebro.models.base.utils.create_from_dict',
        side_effect=FailToCreateError([api_ex]),
    )
    payload = {
        'tlp': 2,
        'pap': 2,
        'dataType': 'hostname',
        'data': 'x',
        'parameters': {'organisation': 'org', 'user': 'nobody@nowhere.io'},
    }
    r = client.post('/api/analyzer/bar/run', json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'Failure'
    assert body['report']['success'] is False
    assert 'SHA256' in body['report']['errorMessage']
    job_id = body['id']
    assert job_id.startswith('cerebro-local-')
    wr = client.get(f'/api/job/{job_id}/waitreport')
    assert wr.status_code == 200
    assert wr.json()['report']['errorMessage'] == body['report']['errorMessage']


def test_run_analyzer_flat_cortex_body(default_workers, k8s_create_job):
    """Cortex analyzer run: flat dataType + data string (TheHive default for observables)."""
    payload = {
        'tlp': 2,
        'pap': 2,
        'dataType': 'hostname',
        'message': '~2',
        'data': 'VJ2C9N',
        'parameters': {'organisation': 'org', 'user': 'nobody@nowhere.io'},
    }
    r = client.post('/api/analyzer/bar/run', json=payload)
    assert r.status_code == 200
    body = r.json()
    assert 'id' in body
    assert body.get('status') == 'Waiting'
    assert body.get('dataType') == 'hostname'
    manifest = k8s_create_job.call_args[0][1]
    env = {
        e['name']: e['value']
        for e in manifest['spec']['template']['spec']['containers'][0].get('env', [])
        if isinstance(e, dict) and 'name' in e
    }
    assert env['CEREBRO_INVOCATION_TYPE'] == 'analyzer'
    assert env['CEREBRO_OBJECT_TYPE'] == 'observable:hostname'
    assert env['CEREBRO_OBJECT_VALUE'] == 'VJ2C9N'
    assert env['CEREBRO_CONTEXT_TYPE'] == ''
    assert env['CEREBRO_CONTEXT_ID'] == ''


def test_run_responder_with_case(default_workers, k8s_create_job):
    """Run a responder with a case artifact."""
    case_artifact = {
        'dataType': 'thehive:case_artifact',
        'data': {
            'id': "~1",
            'dataType': 'filename',
            'data': 'test.txt',
            'case': {
                'id': "~2",
                'createdAt': 1702035312467,
                'createdBy': 'somebody@nowhere.io',
                'description': "This is a case",
                'extendedStatus': "New",
                'owner': 'somebody@nowhere.io',
                'stage': "New",
                'startDate': 1702035300765,
                'status': "Open",
                'title': "My case",
                'updatedAt': 1702317516691,
                'updatedBy': 'somebody@nowhere.io'
            },
        },
        'parameters': {'organisation': 'org', 'user': 'nobody@nowhere.io'},
    }
    r = client.post('/api/responder/foo/run', json=case_artifact)
    assert r.status_code == 200

def test_run_responder_with_alert(default_workers, k8s_create_job):
    """Run a responder with a case artifact."""
    artifact = {
        'dataType': 'thehive:case_artifact',
        'data': {
            'id': "~1",
            'dataType': 'filename',
            'data': 'test.txt',
            'alert': {
                'id': "~2",
                'createdAt': 1702035312467,
                'createdBy': 'somebody@nowhere.io',
                'source': 'somewhere',
                'sourceRef': '1234',
                'description': "This is a case",
                'owner': 'somebody@nowhere.io',
                'stage': "New",
                'startDate': 1702035300765,
                'status': "New",
                'title': "My alert",
                'updatedAt': 1702317516691,
                'updatedBy': 'somebody@nowhere.io'
            },
        },
        'parameters': {'organisation': 'org', 'user': 'nobody@nowhere.io'},
    }
    r = client.post('/api/responder/foo/run', json=artifact)
    assert r.status_code == 200

    manifest = k8s_create_job.call_args[0][1]
    env = {
        e['name']: e['value']
        for e in manifest['spec']['template']['spec']['containers'][0].get('env', [])
        if isinstance(e, dict) and 'name' in e
    }
    assert env['CEREBRO_INVOCATION_TYPE'] == 'responder'
    assert env['CEREBRO_OBJECT_TYPE'] == 'observable:filename'
    assert env['CEREBRO_OBJECT_ID'] == '~1'
    assert env['CEREBRO_CONTEXT_TYPE'] == 'alert'
    assert env['CEREBRO_CONTEXT_ID'] == '~2'


def test_waitreport_when_fetch_fails_returns_failure_with_report(mocker):
    mocker.patch(
        'cerebro.models.base.K8sJob.fetch',
        side_effect=JobExecutionError("Can't access job missing in kube"),
    )
    r = client.get('/api/job/missing-id/waitreport')
    assert r.status_code == 200
    body = r.json()
    assert body['id'] == 'missing-id'
    assert body['status'] == 'Failure'
    assert body['report']['success'] is False
    assert 'missing in kube' in body['report']['errorMessage']


def test_job_status_when_fetch_fails_reports_failure(mocker):
    mocker.patch(
        'cerebro.models.base.K8sJob.fetch',
        side_effect=JobExecutionError('unavailable'),
    )
    r = client.post('/api/job/status', json={'jobIds': ['j1', 'j2']})
    assert r.status_code == 200
    assert r.json() == {'j1': 'Failure', 'j2': 'Failure'}
