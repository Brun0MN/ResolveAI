import pytest
from app.catalog import SCENARIOS, AUTO_ACTIONS, APPROVAL_ACTIONS
from app import storage

@pytest.mark.parametrize('scenario',list(SCENARIOS))
def test_resolve_each_scenario_with_policy(environment,scenario):
    agent,_=environment
    case=SCENARIOS[scenario]
    iid=agent.triage.create(case.title,case.description,scenario)
    result=agent.run(iid)
    assert result['model']=='regras-offline'
    assert result['execution_mode']=='offline-rules'
    assert result['recommended_action']==case.operation
    if case.operation == 'escalate':
        assert result['status']=='escalado'
        assert not any(e['kind']=='operation' for e in result['events'])
        return
    if case.operation in APPROVAL_ACTIONS:
        assert result['status']=='aguardando_aprovacao'
        assert not any(e['kind']=='operation' for e in result['events'])
        result=agent.approve(iid)
        assert result['approved']==1
    assert result['status']=='resolvido'
    assert any(e['kind']=='post_check' and e['detail']['healthy'] for e in result['events'])

def test_rejection_escalates_without_operation(environment):
    agent,_=environment
    iid=agent.triage.create('Falha banco','Falha na API do banco de dados','db_pool_exhausted')
    assert agent.run(iid)['status']=='aguardando_aprovacao'
    result=agent.reject(iid)
    assert result['status']=='escalado'
    assert not any(e['kind']=='operation' for e in result['events'])

def test_duplicate_run_disallowed(environment):
    agent,_=environment
    iid=agent.triage.create('Falha serviço','Aplicação indisponível há minutos','web_stopped')
    agent.run(iid)
    with pytest.raises(Exception): agent.run(iid)

def test_stat_computation(environment):
    agent,_=environment
    iid=agent.triage.create('Serviço web down','Usuários recebem 503 ao navegar','web_stopped')
    assert storage.stats()['total']==1
    assert storage.stats()['rate_pct']==0
    agent.run(iid)
    assert storage.stats()['resolved']==1
    assert storage.stats()['rate_pct']==100
