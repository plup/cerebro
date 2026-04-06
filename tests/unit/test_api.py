"""Module testing the fastapi response validation."""
from time import sleep
from fastapi.testclient import TestClient
from cerebro.api import app
from cerebro.models.cortex import *

client = TestClient(app)

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


def test_job_callback_stores_report(monkeypatch):
    monkeypatch.setenv('CEREBRO_CALLBACK_SECRET', 'test-secret')
    r = client.post(
        '/api/job/my-job-id/callback',
        json={'success': True, 'full': {'message': 'ok'}},
        headers={'Authorization': 'Bearer test-secret'},
    )
    assert r.status_code == 200
    from cerebro.job_callback import get_stored_report

    assert get_stored_report('my-job-id') == {'success': True, 'full': {'message': 'ok'}}


def test_job_callback_rejects_bad_token(monkeypatch):
    monkeypatch.setenv('CEREBRO_CALLBACK_SECRET', 'test-secret')
    r = client.post(
        '/api/job/my-job-id/callback',
        json={'success': True},
        headers={'Authorization': 'Bearer wrong'},
    )
    assert r.status_code == 403


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
    assert (manifest['spec']['template']['spec']['containers'][0]['args'] ==
            ['--object-type', 'observable:filename',
             '--object-id', '~1',
             '--context-type', 'alert',
             '--context-id', '~2']
            )
