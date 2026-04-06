import pytest
from cerebro.models.base import Worker, K8sJob, ThehiveArtefact, WorkerConfigurationError, JobExecutionError
from cerebro.models.cortex import Analyzer, Responder, CortexJob

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

    def test_analyzer_case(self):
        event = {'tlp': 2, 'pap': 2, 'dataType': 'hostname', 'message': '5', 'data': 'VJ2C9N', 'parameters': {'organisation': 'blue team', 'user': 'user@thehive.local'}}
        artefact = ThehiveArtefact.from_analyzer_event(event)
        assert artefact.type == 'observable:hostname'
        assert artefact.id == 'VJ2C9N'
        assert artefact.ctx_type == 'case'
        assert artefact.ctx_id == '5'

    def test_analyzer_flat_explicit_id(self):
        """Prefer root id over data when TheHive sends an observable id."""
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

    def test_analyzer_rejects_nested_thehive_datatype(self):
        with pytest.raises(ValueError, match='flat observable'):
            ThehiveArtefact.from_analyzer_event(
                {
                    'dataType': 'thehive:case_artifact',
                    'data': {},
                    'parameters': {'user': 'u@x'},
                }
            )


class TestJob():
    """Test the job executed by Kubernetes."""
    def test_base(self, default_workers, k8s_create_job):
        """Test the jobs as defined by cerebro."""
        job = K8sJob.create(
            'foo',
            ThehiveArtefact.model_construct(type='thehive:case_artifact', id='~1'),
        )
        assert job.status == 'Waiting'
