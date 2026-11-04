"""Release consistency, frozen oracle separation, simulated provider failure tests."""
import json
from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest

from app import intelligence, reserved_eval, holdout_eval
from app.main import app
from app.release import policy_digest, policy_status, version
from app.reserved_cases import CASES
from app.catalog import ALLOWED_ACTIONS
from scripts import reserved

FROZEN_SHA256='09ca2a46eb56b5d0d2aa2aca22a62deaef5f7beac9988a5e5fc3bf4b0e31edd5'


def test_release_version_single_source_of_truth():
    assert version() == '2.8.0'
    assert app.version == version()
    with TestClient(app) as client:
        result=client.get('/api/config')
    assert result.status_code == 200
    assert result.json()['version'] == version()
    assert result.json()['policy_sha256_prefix'] == policy_digest()


def test_policy_status_checks_digest_not_release_version():
    assert policy_status({'summary':{'version':'2.5.0'},'policy_sha256_prefix':policy_digest()}) == 'match'
    assert policy_status({'summary':{'version':'2.7.0'},'policy_sha256_prefix':'0'*16}) == 'changed'
    assert policy_status({'summary':{'version':'2.7.0'}}) == 'unknown'


def test_frozen_suite_is_fixed_distinct_and_read_only():
    assert len(CASES) == 20
    assert len(set(x.key for x in CASES)) == 20
    assert all(x.key.startswith('RES-') for x in CASES)
    assert reserved.fixture_hash() == FROZEN_SHA256
    assert all(x.expected_action in ALLOWED_ACTIONS | {'escalate'} for x in CASES)
    assert sum(x.expected_action == 'escalate' for x in CASES) >= 9
    assert sum(x.adversarial for x in CASES) >= 2
    for case in CASES:
        description,evidence=case.model_input()
        content=json.dumps([description,evidence],ensure_ascii=False)
        assert case.key not in content
        assert case.explanation not in content
        assert 'expected_action' not in content
        assert set(evidence) == {'check_health','read_logs','read_metrics','read_config'}


def test_frozen_batch_does_not_mutate_lab(tmp_path,monkeypatch):
    monkeypatch.setattr(reserved_eval,'config',SimpleNamespace(database_path=str(tmp_path/'fixture.sqlite3')))
    def forbidden(*args,**kwargs):
        raise AssertionError('This evaluation must never invoke lab tools')
    from app import lab_client
    monkeypatch.setattr(lab_client.LabClient,'operate',forbidden)
    monkeypatch.setattr(lab_client.LabClient,'create',forbidden)
    report=reserved.run_cases('offline',3,0,sleep=lambda _:None)
    assert report['summary']['cases'] == 3
    assert report['summary']['api_errors'] == 0
    assert report['fixture_sha256'] == FROZEN_SHA256
    assert 'GEMINI_API_KEY' not in json.dumps(report)
    with TestClient(app) as client:
        result=client.get('/api/reserved/latest')
    assert result.status_code == 200
    assert result.json()['available'] is True
    assert result.json()['policy_status'] == 'match'
    assert result.json()['summary']['version'] == version()


def test_old_holdout_summary_doesnt_trigger_false_stale(tmp_path,monkeypatch):
    monkeypatch.setattr(holdout_eval,'config',SimpleNamespace(database_path=str(tmp_path/'test.sqlite3')))
    report={'summary':{'version':'2.5.0','cases':1},'details':[],
            'policy_sha256_prefix':policy_digest()}
    holdout_eval.save(report)
    assert holdout_eval.latest()['policy_status'] == 'match'
    assert holdout_eval.latest()['summary']['version'] == '2.5.0'


class ServerError(Exception):
    def __init__(self):
        super().__init__('SECRET-PROVIDER-BODY-APIKEY')
        self.code=503


class ReadTimeout(Exception):
    pass


@pytest.mark.parametrize('error_type', [ServerError, ReadTimeout])
def test_provider_failure_simulation_stops_after_three_attempts(error_type,monkeypatch):
    class Models:
        calls=0
        def generate_content(self,**kwargs):
            self.calls+=1
            raise error_type()
    models=Models()
    delays=[];events=[]
    monkeypatch.setattr(intelligence.time,'sleep',delays.append)
    with intelligence.diagnostic_progress(events.append):
        with pytest.raises(error_type):
            intelligence._generate_with_retry(SimpleNamespace(models=models),model='mock')
    assert models.calls == 3
    assert delays == [1,2]
    assert sum('iniciada' in e for e in events) == 3
    assert any('falha final' in e for e in events)
    assert 'SECRET-PROVIDER-BODY-APIKEY' not in str(events)


def test_frozen_suite_api_error_is_not_counted_as_correct(tmp_path,monkeypatch):
    monkeypatch.setattr(reserved_eval,'config',SimpleNamespace(database_path=str(tmp_path/'test.sqlite3')))
    def fail(*args): raise ServerError()
    result=reserved.run_cases('ai',limit=2,delay=0,diagnose_ai=fail,sleep=lambda _:None)
    assert result['summary']['api_errors'] == 2
    assert result['summary']['answered_cases'] == 0
    assert result['summary']['model_accuracy_pct'] == 0
    assert result['summary']['policy_accuracy_pct'] == 0


def test_cli_uses_offline_by_default_and_explicit_opt_in():
    with pytest.raises(SystemExit):reserved.main(['--mode','ai','--limit','1'])
    with pytest.raises(SystemExit):reserved.main(['--mode','offline','--limit','21'])
