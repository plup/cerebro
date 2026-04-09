import pytest
from unittest.mock import Mock
from datetime import datetime


@pytest.fixture(autouse=True)
def cerebro_api_key_env(monkeypatch):
    """TheHive/Cortex routes require ``Authorization: Bearer`` matching ``CEREBRO_API_KEY``."""
    monkeypatch.setenv('CEREBRO_API_KEY', 'test-cortex-key')


@pytest.fixture()
def default_workers(mocker):
    """Create a fake list of workers."""
    workers = [
        {
            'name': 'foo',
            'type': 'responder',
            'triggers': ['observable:filename', 'observable:hostname'],
            'manifest': {
                'apiVersion': 'batch/v1',
                'kind': 'Job',
                'metadata': {
                    'generateName': 'cerebro-job-',
                },
                'spec': {
                    'backofflimit': 0,
                    'template': {
                        'spec': {
                            'restartPolicy': 'Never',
                            'containers': [
                                {
                                    'name': 'job',
                                    'image': 'job:latest',
                                    'imagePullPolicy':'Never',
                                    'env': [
                                        {'name': 'TH_URL', 'value': 'http://thehive:9000'},
                                        {'name': 'TH_KEY', 'value': 'secret'},
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        },
        {
            'name': 'bar',
            'type': 'analyzer',
            'triggers': ['observable:filename', 'observable:hostname'],
            'manifest': {
                'apiVersion': 'batch/v1',
                'kind': 'Job',
                'metadata': {
                    'generateName': 'cerebro-job-',
                },
                'spec': {
                    'backofflimit': 0,
                    'template': {
                        'spec': {
                            'restartPolicy': 'Never',
                            'containers': [
                                {
                                    'name': 'job',
                                    'image': 'job:latest',
                                    'imagePullPolicy':'Never',
                                    'env': [
                                        {'name': 'TH_URL', 'value': 'http://thehive:9000'},
                                        {'name': 'TH_KEY', 'value': 'secret'},
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        },
    ]
    mocker.patch('cerebro.models.base.read_worker_config', return_value=workers)

@pytest.fixture()
def create_worker():
    """Build a busybox manifest with custom command and args."""
    def _build_manifest(image, command=None, args=[]):
        worker = {
            'name': image,
            'type': 'responder',
            'triggers': [],
            'manifest': {
                'apiVersion': 'batch/v1',
                'kind': 'Job',
                'metadata': {
                    'generateName': 'cerebro-job-',
                    'labels': {'env': 'test'},
                },
                'spec': {
                    'backoffLimit': 0,
                    'template': {
                        'spec': {
                            'restartPolicy': 'Never',
                            'containers': [
                                {
                                    'name': 'job',
                                    'image': image,
                                    'args': args,
                                }
                            ]
                        }
                    }
                }
            }
        }
        if command:
            worker['manifest']['spec']['template']['spec']['containers'][0]['command'] = command
        return worker

    return _build_manifest

@pytest.fixture()
def k8s_create_job(mocker):
    """Return a partial fake job from the kubernetes API."""
    # disable the configuration fetching
    mocker.patch('cerebro.models.base.K8sJob.load_kube_config', return_value='default')

    # return the fake API response
    api_job = Mock(metadata=Mock(creation_timestamp=datetime.now()))
    api_job.metadata.name = 'job' # 'name' is a reserved attribute for mocks
    yield mocker.patch('cerebro.models.base.utils.create_from_dict', return_value=[api_job])
