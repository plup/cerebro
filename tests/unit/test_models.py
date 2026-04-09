import pytest
from datetime import datetime
from cerebro.models.base import Worker, K8sJob, ThehiveArtefact, WorkerConfigurationError, JobExecutionError
from cerebro.models.cortex import Analyzer, Responder, CortexJob, NO_CALLBACK_REPORT_MESSAGE

class TestWorker():
    """Test the worker configuration."""
    def test_search(self, default_workers):
        """Searching on types should only yield the matching type."""
        assert len(Worker.list_workers()) == 2
        assert len(Worker.search(trigger='observable:hostname')) == 2

    def test_responder(self, default_workers):
        assert len(Responder.listall()) == 1
        assert 'thehive:case_artifact' in Responder.get('foo').dataTypeList


class TestThehiveArtefact():
    """TheHive event payloads flattened to type/id (+ optional context)."""

    def test_responder_alert(self):
        event = {'label': '[test:1] alert title', 'data': {'_id': '~122916928', 'id': '~122916928', 'createdBy': 'user@thehive.local', 'updatedBy': 'user@thehive.local', 'createdAt': 1772119700077, 'updatedAt': 1775241410222, '_type': 'alert', 'type': 'alertType', 'source': 'test', 'sourceRef': '1', 'externalLink': None, 'case': None, 'title': 'alert title', 'description': 'alert description', 'severity': 2, 'date': 1772119700001, 'tags': [], 'tlp': 2, 'pap': 2, 'status': 'New', 'stage': 'New', 'follow': True, 'customFields': {}, 'caseTemplate': None, 'artifacts': [], 'similarCases': [], 'summary': None, 'severityLabel': 'MEDIUM', 'tlpLabel': 'AMBER', 'papLabel': 'AMBER', 'assignee': None, 'customFieldValues': {}}, 'dataType': 'thehive:alert', 'tlp': 2, 'pap': 2, 'parameters': {'organisation': 'blue team', 'user': 'user@thehive.local'}}
        artefact = ThehiveArtefact.from_responder_event(event)
        assert artefact.type == 'alert'
        assert artefact.id == '~122916928'
        assert artefact.ctx_type == ''
        assert artefact.ctx_id == ''

    def test_responder_case(self):
        event = {'label': '#5 Test', 'data': {'_id': '~40992960', 'id': '~40992960', 'createdBy': 'service@thehive.local', 'updatedBy': 'service@thehive.local', 'createdAt': 1772542872110, 'updatedAt': 1772542923109, '_type': 'case', 'caseId': 5, 'title': 'Test', 'description': 'This is a test', 'severity': 2, 'startDate': 1772542872039, 'endDate': None, 'impactStatus': None, 'resolutionStatus': None, 'tags': ['triage'], 'flag': False, 'tlp': 2, 'pap': 2, 'status': 'Open', 'extendedStatus': 'New', 'stage': 'New', 'summary': None, 'owner': 'service@thehive.local', 'customFields': {}, 'stats': {}, 'permissions': [], 'severityLabel': 'MEDIUM', 'tlpLabel': 'AMBER', 'papLabel': 'AMBER', 'assignee': 'service@thehive.local', 'customFieldValues': {}}, 'dataType': 'thehive:case', 'tlp': 2, 'pap': 2, 'parameters': {'organisation': 'blue team', 'user': 'user@thehive.local'}}
        artefact = ThehiveArtefact.from_responder_event(event)
        assert artefact.type == 'case'
        assert artefact.id == '~40992960'
        assert artefact.ctx_type == ''
        assert artefact.ctx_id == ''

    def test_responder_case_artifact_from_alert(self):
        event = {'label': '[hostname] VJ2C9N', 'data': {'_id': '~40964240', 'id': '~40964240', 'createdBy': 'user@thehive.local', 'createdAt': 1775241409850, '_type': 'case_artifact', 'dataType': 'hostname', 'data': 'VJ2C9N', 'startDate': 1775241409850, 'tlp': 2, 'pap': 2, 'tags': [], 'ioc': False, 'sighted': False, 'message': '', 'reports': {}, 'stats': {}, 'ignoreSimilarity': False, 'alert': {'_id': '~122916928', 'id': '~122916928', 'createdBy': 'user@thehive.local', 'updatedBy': 'user@thehive.local', 'createdAt': 1772119700077, 'updatedAt': 1775241410222, '_type': 'alert', 'type': 'alertType', 'source': 'test', 'sourceRef': '1', 'externalLink': None, 'case': None, 'title': 'alert title', 'description': 'alert description', 'severity': 2, 'date': 1772119700001, 'tags': [], 'tlp': 2, 'pap': 2, 'status': 'New', 'stage': 'New', 'follow': True, 'customFields': {}, 'caseTemplate': None, 'artifacts': [], 'similarCases': [], 'summary': None, 'severityLabel': 'MEDIUM', 'tlpLabel': 'AMBER', 'papLabel': 'AMBER', 'assignee': None, 'customFieldValues': {}}}, 'dataType': 'thehive:case_artifact', 'tlp': 2, 'pap': 2, 'parameters': {'organisation': 'blue team', 'user': 'user@thehive.local'}}
        artefact = ThehiveArtefact.from_responder_event(event)
        assert artefact.type == 'observable:hostname'
        assert artefact.id == '~40964240'
        assert artefact.ctx_type == 'alert'
        assert artefact.ctx_id == '~122916928'

    def test_responder_case_artifact_from_case(self):
        event = {'label': '[hostname] VJ2C9N', 'data': {'_id': '~81940608', 'id': '~81940608', 'createdBy': 'user@thehive.local', 'createdAt': 1775260612833, '_type': 'case_artifact', 'dataType': 'hostname', 'data': 'VJ2C9N', 'startDate': 1775260612833, 'tlp': 2, 'pap': 2, 'tags': [], 'ioc': False, 'sighted': False, 'message': '', 'reports': {}, 'stats': {}, 'ignoreSimilarity': False, 'case': {'_id': '~40992960', 'id': '~40992960', 'createdBy': 'service@thehive.local', 'updatedBy': 'user@thehive.local', 'createdAt': 1772542872110, 'updatedAt': 1775260612852, '_type': 'case', 'caseId': 5, 'title': 'Test', 'description': 'This is a test', 'severity': 2, 'startDate': 1772542872039, 'endDate': None, 'impactStatus': None, 'resolutionStatus': None, 'tags': ['triage'], 'flag': False, 'tlp': 2, 'pap': 2, 'status': 'Open', 'extendedStatus': 'New', 'stage': 'New', 'summary': None, 'owner': 'service@thehive.local', 'customFields': {}, 'stats': {}, 'permissions': [], 'severityLabel': 'MEDIUM', 'tlpLabel': 'AMBER', 'papLabel': 'AMBER', 'assignee': 'service@thehive.local', 'customFieldValues': {}}}, 'dataType': 'thehive:case_artifact', 'tlp': 2, 'pap': 2, 'parameters': {'organisation': 'blue team', 'user': 'user@thehive.local'}}
        artefact = ThehiveArtefact.from_responder_event(event)
        assert artefact.type == 'observable:hostname'
        assert artefact.id == '~81940608'
        assert artefact.ctx_type == 'case'
        assert artefact.ctx_id == '~40992960'

    def test_analyzer_flat_explicit_id(self):
        """TheHive ``id`` is stored separately from the observable ``data`` string."""
        event = {
            'tlp': 2,
            'pap': 2,
            'dataType': 'ip',
            'data': '1.2.3.4',
            'id': '~999',
            'parameters': {'user': 'u@x'},
        }
        artefact = ThehiveArtefact.from_analyzer_event(event)
        assert artefact.type == 'observable:ip'
        assert artefact.id == '~999'
        assert artefact.data == '1.2.3.4'

    def test_analyzer_rejects_nested_thehive_datatype(self):
        with pytest.raises(ValueError, match='flat observable'):
            ThehiveArtefact.from_analyzer_event(
                {
                    'dataType': 'thehive:case_artifact',
                    'data': {},
                    'parameters': {'user': 'u@x'},
                }
            )


class TestCortexJobReport():
    """Callback report overrides log-derived report when the job is finished."""

    def test_report_uses_callback_payload_when_done(self):
        w = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
        job = CortexJob(
            id='j1',
            worker=w,
            object_type='observable:hostname',
            kube_status='Success',
            started=datetime.now(),
            message='',
            callback_report={'success': True, 'full': {'message': 'from callback'}},
        )
        assert job.report['full']['message'] == 'from callback'

    def test_report_injects_success_when_callback_omits_key(self):
        w = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
        ok = CortexJob(
            id='j-ok',
            worker=w,
            object_type='observable:hostname',
            kube_status='Success',
            started=datetime.now(),
            message='',
            callback_report={'full': {'message': 'done'}},
        )
        assert ok.report == {'success': True, 'full': {'message': 'done'}}
        bad = CortexJob(
            id='j-bad',
            worker=w,
            object_type='observable:hostname',
            kube_status='Failure',
            started=datetime.now(),
            message='',
            callback_report={'full': {'message': 'failed'}},
        )
        assert bad.report == {'success': False, 'full': {'message': 'failed'}}

    def test_report_placeholder_without_callback(self):
        w = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
        ok = CortexJob(
            id='j3',
            worker=w,
            object_type='observable:hostname',
            kube_status='Success',
            started=datetime.now(),
            message='',
            callback_report=None,
        )
        assert ok.report == {'success': True, 'full': {'message': NO_CALLBACK_REPORT_MESSAGE}}
        bad = CortexJob(
            id='j4',
            worker=w,
            object_type='observable:hostname',
            kube_status='Failure',
            started=datetime.now(),
            message='',
            callback_report=None,
        )
        assert bad.report == {
            'success': False,
            'errorMessage': f'Job failed; check the Kubernetes job j4.',
        }

    def test_report_ignores_callback_while_in_progress(self):
        w = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
        job = CortexJob(
            id='j2',
            worker=w,
            object_type='observable:hostname',
            kube_status='InProgress',
            started=datetime.now(),
            message='',
            callback_report={'success': True, 'full': {'message': 'early'}},
        )
        assert job.report == {}


class TestCortexJobStatus():
    """``status`` for TheHive follows callback ``success`` when present, else ``kube_status``."""

    def test_status_follows_callback_when_present(self):
        w = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
        job = CortexJob(
            id='j-cb',
            worker=w,
            object_type='observable:hostname',
            kube_status='Success',
            started=datetime.now(),
            message='',
            callback_report={'success': False, 'full': {'message': 'logic failure'}},
        )
        assert job.status == 'Failure'

    def test_status_matches_kube_without_callback(self):
        w = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
        fail = CortexJob(
            id='j-kf',
            worker=w,
            object_type='observable:hostname',
            kube_status='Failure',
            started=datetime.now(),
            message='',
            callback_report=None,
        )
        assert fail.status == 'Failure'


class TestJob():
    """Test the job executed by Kubernetes."""
    def test_base(self, default_workers, k8s_create_job):
        """Test the jobs as defined by cerebro."""
        job = K8sJob.create(
            'foo',
            ThehiveArtefact.model_construct(type='thehive:case_artifact', id='~1'),
        )
        assert job.kube_status == 'Waiting'
