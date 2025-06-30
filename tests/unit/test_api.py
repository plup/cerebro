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

def test_list_responder(default_workers):
    r = client.post('/api/responder/_search')
    assert r.status_code == 200

def test_get_responder(default_workers):
    r = client.get('/api/responder/foo')
    assert r.status_code == 200

def test_get_nothing():
    r = client.get('/api/analyzer/nothing')
    assert r.status_code == 404

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
            ['--object-type', 'thehive:case_artifact',
             '--object-id', '~1',
             '--context-type', 'alert',
             '--context-id', '~2']
            )
