import pytest
from cerebro.models.base import Worker, K8sJob, WorkerConfigurationError, JobExecutionError
from cerebro.models.cortex import Analyzer, Responder, CortexJob

class TestWorker():
    """Test the worker configuration."""
    def test_search(self, default_workers):
        """Searching on types should only yield the matching type."""
        assert len(Worker.list()) == 1
        assert len(Worker.search(trigger='observable:hostname')) == 1

    def test_responder(self, default_workers):
        assert len(Responder.listall()) == 1
        assert 'thehive:case_artifact' in Responder.get('foo').dataTypeList


class TestJob():
    """Test the job executed by Kubernetes."""
    def test_base(self, default_workers, k8s_create_job):
        """Test the jobs as defined by cerebro."""
        job = K8sJob.create('foo', 'thehive:case_artifact', '~1')
        assert job.status == 'Waiting'
