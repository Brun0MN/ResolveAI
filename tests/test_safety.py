import pytest
from app import workflow, storage
from app.intelligence import Diagnosis


def test_model_error_fails_closed(environment,monkeypatch):
    agent,_=environment
    def bad_model(*args): raise RuntimeError('API indisponível')
    monkeypatch.setattr(workflow,'diagnose',bad_model)
    iid=agent.triage.create('Serviço indisponível','Sistema apresenta erro 503 desde hoje','web_stopped')
    result=agent.run(iid)
    assert result['status']=='escalado'
    assert not any(e['kind']=='operation' for e in result['events'])
    assert any(e['kind']=='error' for e in result['events'])


def test_invalid_model_action_is_not_executed(environment,monkeypatch):
    agent,_=environment
    def bad_plan(*args):
        return Diagnosis(category='Aplicação',severity='alta',root_cause='Desconhecida',rationale='Teste de allowlist',action='rm -rf /',confidence=1.0,needs_human=False,evidence=[]),'gemini:mock'
    monkeypatch.setattr(workflow,'diagnose',bad_plan)
    iid=agent.triage.create('Aplicação com falha','O portal não funciona corretamente','web_stopped')
    result=agent.run(iid)
    assert result['status']=='escalado'
    assert not any(e['kind']=='operation' for e in result['events'])


def test_low_confidence_escalates_even_with_valid_action(environment,monkeypatch):
    agent,_=environment
    def uncertain(*args):
        return Diagnosis(category='Aplicação',severity='alta',root_cause='Talvez processo inativo',rationale='Sem confirmação',action='restart_demo_web',confidence=0.1,needs_human=False,evidence=[]),'gemini:mock'
    monkeypatch.setattr(workflow,'diagnose',uncertain)
    iid=agent.triage.create('Aplicação com falha','Serviço não responde ao usuário','web_stopped')
    result=agent.run(iid)
    assert result['status']=='escalado'
    assert not any(e['kind']=='operation' for e in result['events'])


def test_wrong_allowlisted_action_never_claims_success(environment,monkeypatch):
    agent,_=environment
    def wrong(*args):
        return Diagnosis(category='Rede/DNS',severity='alta',root_cause='DNS inválido',rationale='Simulação do erro do modelo',action='restore_demo_dns',confidence=0.99,needs_human=False,evidence=[]),'gemini:mock'
    monkeypatch.setattr(workflow,'diagnose',wrong)
    iid=agent.triage.create('Serviço com erro','Servidor web não está disponível','web_stopped')
    result=agent.run(iid)
    assert result['status']=='escalado'
    assert not any(e['kind']=='operation' for e in result['events'])
    assert any(e['kind']=='evidence_gate' and e['detail']['permitted'] is False for e in result['events'])
