"""Actual HTTP worker subprocess tests (no Docker daemon needed)."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.config import config
from real_lab.main import app, REAL_SCENARIOS
from app.policy import check_evidence

@pytest.mark.parametrize('scenario', list(REAL_SCENARIOS))
def test_real_worker_crash_and_recovery(scenario):
    headers={'X-Lab-Token':config.lab_token}
    iid=str(uuid4())
    with TestClient(app) as client:
        assert client.post('/target/incidents',headers=headers,
            json={'id':iid,'scenario':scenario}).status_code==201
        before=client.get(f'/target/incidents/{iid}/health',headers=headers).json()
        assert not before['healthy']
        assert before['backend']=='process-isolated'
        logs=client.get(f'/target/incidents/{iid}/logs',headers=headers).json()
        assert logs['lines']
        observations={
            'check_health':before,
            'read_logs':logs,
            'read_metrics':client.get(f'/target/incidents/{iid}/metrics',headers=headers).json(),
            'read_config':client.get(f'/target/incidents/{iid}/config',headers=headers).json(),
        }
        assert check_evidence(REAL_SCENARIOS[scenario][1], observations).permitted
        wrong=client.post(f'/target/incidents/{iid}/operate',headers=headers,
            json={'operation':'delete-all-files'}).json()
        assert not wrong['applied']
        assert not client.get(f'/target/incidents/{iid}/health',headers=headers).json()['healthy']
        right=client.post(f'/target/incidents/{iid}/operate',headers=headers,
            json={'operation':REAL_SCENARIOS[scenario][1]}).json()
        assert right['applied'],right
        after=client.get(f'/target/incidents/{iid}/health',headers=headers).json()
        assert after['healthy'] and after['http_status']==200
        assert after['process_alive']

def test_real_worker_needs_auth():
    with TestClient(app) as client:
        assert client.post('/target/incidents',json={'id':str(uuid4()),'scenario':'web_stopped'}).status_code==403
