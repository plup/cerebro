import pytest
from time import sleep
from cerebro.models.cerebro import K8sJob

def test_kube_success(create_worker, mocker):
    """Run a job in kubernetes with a successful status."""
    # force job to return true
    worker = create_worker('busybox', ['true'])
    mocker.patch('cerebro.models.cerebro.Worker._load', return_value=[worker])

    # run the job
    job = K8sJob.create('busybox', '', '')
    timeout = 0
    while (job.status == 'Waiting' or job.status == 'InProgress')  and timeout <= 30:
        sleep(5)
        timeout += 5
        job = K8sJob.fetch(job.id)

    assert job.status == 'Success'

def test_kube_logs(create_worker, mocker):
    """Run a job in kubernetes and check log output."""
    # generate a multiline output in the job
    worker = create_worker('busybox', ['echo', "hello\nworld"])
    mocker.patch('cerebro.models.cerebro.Worker._load', return_value=[worker])

    # run the job
    job = K8sJob.create('busybox', '', '')
    timeout = 0
    while (job.status == 'Waiting' or job.status == 'InProgress')  and timeout <= 30:
        sleep(5)
        timeout += 5
        job = K8sJob.fetch(job.id)

    assert job.status == 'Success'
    assert 'world' in job.message
    assert 'hello' not in job.message

def test_kube_default_args(create_worker, mocker):
    """Run a job in kubernetes and check the default args are passed."""
    # Create an entrypoint checking for the specific args
    inline_script = 'import sys; \
            assert sys.argv[1] == "--object-type"; \
            assert sys.argv[2] == "artifact"; \
            assert sys.argv[3] == "--object-id"; \
            assert sys.argv[4] == "1234"'
    worker = create_worker('python', command=['python', '-c', inline_script])
    mocker.patch('cerebro.models.cerebro.Worker._load', return_value=[worker])

    # create the job passing the expected args
    job = K8sJob.create('python', 'artifact', '1234')
    timeout = 0
    while (job.status == 'Waiting' or job.status == 'InProgress')  and timeout <= 30:
        sleep(5)
        timeout += 5
        job = K8sJob.fetch(job.id)

    assert job.status == 'Success'

def test_kube_extra_args(create_worker, mocker):
    """
    Run a job in kubernetes and check the existing args are kept.
    """
    # create an entrypoint checking for the args including the one already in the manifest
    inline_script = 'import sys; \
            assert sys.argv[1] == "--extra"; \
            assert len(sys.argv) == 6'
    worker = create_worker('python', command=['python', '-c', inline_script], args=["--extra"])
    mocker.patch('cerebro.models.cerebro.Worker._load', return_value=[worker])

    # create the job passing default args
    job = K8sJob.create('python', 'artifact', '1234')
    timeout = 0
    while (job.status == 'Waiting' or job.status == 'InProgress')  and timeout <= 30:
        sleep(5)
        timeout += 5
        job = K8sJob.fetch(job.id)

    assert job.status == 'Success'
