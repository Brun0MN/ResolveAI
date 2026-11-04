"""Challenge suite is read-only, includes adversarial inputs, and scores objectively."""
import json
from types import SimpleNamespace
from app.challenge_cases import CASES
from app.challenge_eval import score, summarize_challenge, save_challenge, latest_challenge
from app import challenge_eval
from app.catalog import ALLOWED_ACTIONS
from app.intelligence import Diagnosis, rule_based_diagnosis
from scripts.challenge import run_cases


def test_unique_cases_and_expected_actions():
    assert len(CASES)==22
    assert len({c.key for c in CASES})==len(CASES)
    assert all(c.expected_action in ALLOWED_ACTIONS|{'escalate'} for c in CASES)
    assert sum(c.adversarial for c in CASES)>=3
    assert sum(c.expected_action=='escalate' for c in CASES)>=4
    assert len({c.group for c in CASES})>=4


def test_oracle_not_visible_to_model():
    for c in CASES:
        description,evidence=c.model_input()
        payload=json.dumps([description,evidence],ensure_ascii=False)
        assert c.key not in payload
        assert c.explanation not in payload
        assert 'expected_action' not in payload
        assert set(evidence)=={'check_health','read_logs','read_metrics','read_config'}


def test_baseline_uses_actual_evidence_and_misses_paraphrase():
    web=CASES[0]
    description,evidence=web.model_input()
    baseline=rule_based_diagnosis(description,evidence)
    assert baseline.action=='escalate'
    assert baseline.action!=web.expected_action


def test_score_detects_wrong_action_in_unknown_and_approval_bypass():
    unknown=next(c for c in CASES if c.key=='UNKNOWN-04')
    baseline=rule_based_diagnosis(*unknown.model_input())
    bad=Diagnosis(category='?',severity='alta',root_cause='?',rationale='?',action='clear_demo_cache',confidence=.99,needs_human=False,evidence=[])
    row=score(unknown,bad,baseline,'ai',1)
    assert row['correct'] is False
    assert row['unsafe_suggestion'] is True
    approval=next(c for c in CASES if c.key=='DB-01')
    bad=Diagnosis(category='db',severity='alta',root_cause='pool',rationale='pool',action='reset_demo_db_pool',confidence=.8,needs_human=False,evidence=[])
    row=score(approval,bad,rule_based_diagnosis(*approval.model_input()),'ai',1)
    assert row['correct'] is True
    assert row['unsafe_suggestion'] is True


def test_errors_do_not_count_as_success():
    c=CASES[0]
    b=rule_based_diagnosis(*c.model_input())
    row=score(c,None,b,'ai',.1,error='ClientError')
    stats=summarize_challenge([row],'ai')
    assert stats['model_accuracy_pct']==0
    assert stats['api_errors']==1
    assert stats['total_tokens']==0


def test_no_actions_are_executed_even_if_model_suggests_action(tmp_path, monkeypatch):
    monkeypatch.setattr(challenge_eval,'config',SimpleNamespace(database_path=str(tmp_path/'project.sqlite3')))
    calls=[]
    def fake_model(description,evidence):
        calls.append((description,evidence))
        return Diagnosis(category='Teste',severity='média',root_cause='exemplo',rationale='sintético',action='restart_demo_web',confidence=.7,needs_human=False,evidence=[])
    result=run_cases('ai',3,0,diagnose_ai=fake_model,sleep=lambda s:None)
    assert len(calls)==3
    assert len(result['details'])==3
    assert challenge_eval.challenge_path().exists()
    report=latest_challenge()
    assert report['available'] is True
    assert report['summary']['cases']==3
    assert 'gemini_key' not in json.dumps(report)


def test_read_only_endpoint(monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setattr(challenge_eval,'config',SimpleNamespace(database_path=str(tmp_path/'project.sqlite3')))
    with TestClient(app) as client:
        r=client.get('/api/challenge/latest')
        assert r.status_code==200
        assert r.json()['available'] is False


def test_cli_requires_explicit_consent():
    import pytest
    from scripts.challenge import main
    with pytest.raises(SystemExit):
        main(['--mode','ai','--limit','1'])
    with pytest.raises(SystemExit):
        main(['--mode','offline','--limit','999'])
