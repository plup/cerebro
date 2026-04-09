import pytest
from time import sleep

from cerebro.models.base import K8sJob, ThehiveArtefact


def test_kube_success(create_worker, mocker):
    """Run a job in kubernetes with a successful status."""
    worker = create_worker('busybox', ['true'])
    mocker.patch('cerebro.models.base.Worker._load', return_value=[worker])

    job = K8sJob.create(
        'busybox',
        ThehiveArtefact.model_construct(type='case', id='1'),
    )
    timeout = 0
    while (job.status == 'Waiting' or job.status == 'InProgress') and timeout <= 30:
        sleep(5)
        timeout += 5
        job = K8sJob.fetch(job.id)

    assert job.status == 'Success'


def test_kube_logs(create_worker, mocker):
    """Run a job in kubernetes and check log output."""
    worker = create_worker('busybox', ['echo', "hello\nworld"])
    mocker.patch('cerebro.models.base.Worker._load', return_value=[worker])

    job = K8sJob.create(
        'busybox',
        ThehiveArtefact.model_construct(type='case', id='1'),
    )
    timeout = 0
    while (job.status == 'Waiting' or job.status == 'InProgress') and timeout <= 30:
        sleep(5)
        timeout += 5
        job = K8sJob.fetch(job.id)

    assert job.status == 'Success'
    assert 'world' in job.message
    assert 'hello' not in job.message


def test_kube_invocation_env(create_worker, mocker):
    """Run a job in kubernetes and check CEREBRO_* invocation env is set."""
    inline_script = (
        'import os\n'
        'assert os.environ["CEREBRO_INVOCATION_TYPE"] == "responder"\n'
        'assert os.environ["CEREBRO_OBJECT_TYPE"] == "artifact"\n'
        'assert os.environ["CEREBRO_OBJECT_ID"] == "1234"\n'
    )
    worker = create_worker('python', command=['python', '-c', inline_script])
    mocker.patch('cerebro.models.base.Worker._load', return_value=[worker])

    job = K8sJob.create(
        'python',
        ThehiveArtefact.model_construct(type='artifact', id='1234'),
    )
    timeout = 0
    while (job.status == 'Waiting' or job.status == 'InProgress') and timeout <= 30:
        sleep(5)
        timeout += 5
        job = K8sJob.fetch(job.id)

    assert job.status == 'Success'


def test_kube_extra_args(create_worker, mocker):
    """Run a job in kubernetes and keep manifest ``args`` while invocation uses env."""
    inline_script = (
        'import os\n'
        'import sys\n'
        'assert "--extra" in sys.argv\n'
        'assert os.environ["CEREBRO_OBJECT_ID"] == "1234"\n'
    )
    worker = create_worker('python', command=['python', '-c', inline_script], args=['--extra'])
    mocker.patch('cerebro.models.base.Worker._load', return_value=[worker])

    job = K8sJob.create(
        'python',
        ThehiveArtefact.model_construct(type='artifact', id='1234'),
    )
    timeout = 0
    while (job.status == 'Waiting' or job.status == 'InProgress') and timeout <= 30:
        sleep(5)
        timeout += 5
        job = K8sJob.fetch(job.id)

    assert job.status == 'Success'
