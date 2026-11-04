import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app import storage, intelligence, workflow
import lab.main as labmod

@pytest.fixture
def environment(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'config',SimpleNamespace(database_path=str(tmp_path/'incidents.db')))
    monkeypatch.setattr(labmod,'config',SimpleNamespace(lab_database_path=str(tmp_path/'lab.db'),lab_token='test-secret'))
    monkeypatch.setattr(intelligence,'config',SimpleNamespace(gemini_key='',gemini_model='gemini-2.5-flash'))
    labclient=TestClient(labmod.app)
    class LocalLabClient:
        def __init__(self): self.client=labclient
        def create(self,iid,scenario):
            r=self.client.post('/lab/incidents',headers={'X-Lab-Token':'test-secret'},json={'id':iid,'scenario':scenario});r.raise_for_status();return r.json()
        def tool(self,iid,name):
            endpoints={'check_health':'health','read_logs':'logs','read_metrics':'metrics','read_config':'config'}
            r=self.client.get(f'/lab/incidents/{iid}/{endpoints[name]}',headers={'X-Lab-Token':'test-secret'});r.raise_for_status();return r.json()
        def operate(self,iid,operation):
            r=self.client.post(f'/lab/incidents/{iid}/operate',headers={'X-Lab-Token':'test-secret'},json={'operation':operation});r.raise_for_status();return r.json()
    monkeypatch.setattr(workflow,'LabClient',LocalLabClient)
    return workflow.Workflow(),labclient
