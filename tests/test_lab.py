import pytest
from app.catalog import SCENARIOS
from uuid import uuid4

@pytest.mark.parametrize('scenario',list(SCENARIOS))
def test_lab_health_and_correct_fix(environment,scenario):
    _,client=environment
    iid=str(uuid4())
    h={'X-Lab-Token':'test-secret'}
    r=client.post('/lab/incidents',json={'id':iid,'scenario':scenario},headers=h)
    assert r.status_code==201
    assert client.get(f'/lab/incidents/{iid}/health',headers=h).json()['healthy'] is False
    assert client.get(f'/demo/incidents/{iid}/service',headers=h).status_code==503
    bad=client.post(f'/lab/incidents/{iid}/operate',json={'operation':'arbitrary_shell_command'},headers=h)
    assert bad.status_code==403
    op=SCENARIOS[scenario].operation
    if op == 'escalate':
        assert client.post(f'/lab/incidents/{iid}/operate',json={'operation':op},headers=h).status_code==403
        assert client.get(f'/lab/incidents/{iid}/health',headers=h).json()['healthy'] is False
        return
    assert client.post(f'/lab/incidents/{iid}/operate',json={'operation':op},headers=h).json()['applied']
    assert client.get(f'/lab/incidents/{iid}/health',headers=h).json()['healthy'] is True
    assert client.get(f'/demo/incidents/{iid}/service',headers=h).status_code==200

def test_lab_token_is_required(environment):
    _,client=environment
    r=client.post('/lab/incidents',json={'id':str(uuid4()),'scenario':'web_stopped'})
    assert r.status_code==403
