"""Regression tests for the new diagnostic-only holdout suite."""
import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

from app.catalog import ALLOWED_ACTIONS
from app.holdout_cases import CASES
from app import holdout_eval
from app.holdout_eval import score,summary
from app.intelligence import Diagnosis, rule_based_diagnosis
from scripts.holdout import run_cases, main, policy_digest


def fake_diag(action, needs_human=False):
    return Diagnosis(category='Teste',severity='alta',root_cause='Demonstração',
                     rationale='Resultado controlado do teste',action=action,
                     confidence=.9,needs_human=needs_human,evidence=['Exemplo'])


def test_new_set_is_separate_complete_and_fixed():
    assert len(CASES)==28
    assert len({x.key for x in CASES})==len(CASES)
    assert all(x.key.startswith('HOLD-') for x in CASES)
    assert all(x.expected_action in ALLOWED_ACTIONS|{'escalate'} for x in CASES)
    assert sum(x.adversarial for x in CASES)>=4
    assert sum(x.expected_action=='escalate' for x in CASES)>=10


def test_oracles_cannot_enter_model_payload():
    for c in CASES:
        desc,observed=c.model_input()
        payload=json.dumps([desc,observed],ensure_ascii=False)
        assert c.key not in payload
        assert c.explanation not in payload
        assert 'expected_action' not in payload
        assert set(observed)=={'check_health','read_logs','read_metrics','read_config'}


def test_score_detects_unsafe_policy_passthrough():
    # This previously unseen set was reviewed for v2.5; it is now a regression suite.
    case=next(x for x in CASES if x.key=='HOLD-25')
    baseline=rule_based_diagnosis(*case.model_input())
    row=score(case,fake_diag('disable_demo_maintenance'),baseline,'ai',.25)
    assert row['model_correct'] is False
    assert row['unsafe_action_proposed'] is True
    assert row['unsafe_action_not_blocked'] is False
    assert row['policy_correct'] is True


def test_errors_count_as_errors_even_when_escalation_expected():
    case=next(x for x in CASES if x.expected_action=='escalate')
    row=score(case,None,rule_based_diagnosis(*case.model_input()),'ai',1,'ServerError')
    assert row['model_correct'] is False
    assert row['policy_correct'] is False
    assert summary([row],'ai')['api_errors']==1


def test_policy_hash_is_consistent():
    from app import policy
    assert policy_digest()==sha256(Path(policy.__file__).read_bytes()).hexdigest()[:16]


def test_mock_ai_never_calls_mutating_tools(monkeypatch,tmp_path):
    monkeypatch.setattr(holdout_eval,'config',SimpleNamespace(database_path=str(tmp_path/'test.sqlite3')))
    seen=[]
    def model(desc,evidence):
        seen.append((desc,evidence))
        return fake_diag('escalate',True)
    report=run_cases('ai',3,0,diagnose_ai=model,sleep=lambda _:None)
    assert len(seen)==3
    assert report['summary']['cases']==3
    assert report['summary']['api_errors']==0
    assert holdout_eval.latest()['available']
    assert 'GEMINI_API_KEY' not in json.dumps(report)


def test_cli_requires_explicit_api_consent(monkeypatch):
    with pytest.raises(SystemExit):main(['--mode','ai','--limit','1'])
    with pytest.raises(SystemExit):main(['--mode','offline','--limit','500'])


def test_dashboard_reports_not_run(monkeypatch,tmp_path):
    from app.main import app
    monkeypatch.setattr(holdout_eval,'config',SimpleNamespace(database_path=str(tmp_path/'test.sqlite3')))
    with TestClient(app) as client:
        response=client.get('/api/holdout/latest')
    assert response.status_code==200
    assert response.json()['available'] is False
