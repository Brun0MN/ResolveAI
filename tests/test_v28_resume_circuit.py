"""Circuit breaker, checkpoint/resume, and honest statistics (no live API calls)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import reserved_eval
from app.intelligence import Diagnosis
from app.release import policy_digest
from scripts import reserved


class ServerError(Exception):
    def __init__(self, code=503):
        super().__init__('TOP-SECRET-DO-NOT-LOG')
        self.code = code


def output(action='escalate'):
    return Diagnosis(category='Teste', severity='média', root_cause='teste', rationale='teste',
                     action=action, confidence=.7, needs_human=True, evidence=[])


@pytest.fixture
def isolated_report(tmp_path, monkeypatch):
    monkeypatch.setattr(reserved_eval, 'config',
                        SimpleNamespace(database_path=str(tmp_path/'db.sqlite3')))
    return tmp_path / 'reserved_latest.json'


def test_circuit_stops_after_two_api_failures_without_wasting_remaining_calls(isolated_report):
    hits=[]
    def provider(d, e):
        hits.append(1)
        raise ServerError(503)
    report=reserved.run_cases('ai',limit=5,delay=0,diagnose_ai=provider,sleep=lambda _: None)
    assert len(hits) == 2
    assert report['run_status'] == 'paused_api'
    assert report['pause_reason'] == 'servico_temporariamente_indisponivel'
    assert report['summary']['cases'] == 2
    assert report['summary']['target_cases'] == 5
    assert report['summary']['pending_cases'] == 5
    assert report['summary']['api_availability_pct'] == 0
    assert report['summary']['model_accuracy_when_answered_pct'] is None
    assert report['suggested_retry_utc']
    assert json.loads(isolated_report.read_text())['run_status'] == 'paused_api'
    assert 'TOP-SECRET' not in isolated_report.read_text()


def test_resume_reuses_successful_rows_and_retries_errors_only(isolated_report):
    count=0
    def first(d,e):
        nonlocal count
        count += 1
        return output() if count == 1 else (_ for _ in ()).throw(ServerError())
    partial=reserved.run_cases('ai',limit=4,delay=0,diagnose_ai=first,sleep=lambda _:None)
    assert count == 3
    assert partial['summary']['answered_cases'] == 1
    assert partial['summary']['api_errors'] == 2
    calls=[]
    def second(d,e):
        calls.append(d)
        return output()
    resumed=reserved.run_cases('ai',limit=4,delay=0,diagnose_ai=second,
                               sleep=lambda _:None,resume=True)
    assert len(calls) == 3  # do not repeat the successful RES-01
    assert resumed['run_status'] == 'complete'
    assert resumed['summary']['cases'] == 4
    assert resumed['summary']['api_errors'] == 0
    assert resumed['summary']['answered_cases'] == 4
    assert resumed['summary']['api_availability_pct'] == 100
    assert resumed['summary']['previous_error_count'] == 2
    assert resumed['summary']['pending_cases'] == 0
    assert len({r['case_id'] for r in resumed['details']}) == 4


def test_429_is_not_retried_across_more_cases(isolated_report):
    n=[]
    def quota(d,e):
        n.append(1)
        raise ServerError(429)
    report=reserved.run_cases('ai',limit=5,delay=0,diagnose_ai=quota,sleep=lambda _:None)
    assert len(n) == 1
    assert report['run_status'] == 'paused_api'
    assert report['pause_reason'] == 'limite_de_requisicoes'
    assert report['summary']['pending_cases'] == 5


def test_success_resets_consecutive_failure_counter(isolated_report):
    states=[503, None, 503, None]
    def provider(d,e):
        state=states.pop(0)
        if state:
            raise ServerError(state)
        return output()
    report=reserved.run_cases('ai',limit=4,delay=0,diagnose_ai=provider,sleep=lambda _:None)
    assert not states
    assert report['run_status'] == 'paused_api'  # errors can be retried; not complete
    assert report['summary']['answered_cases'] == 2
    assert report['summary']['api_errors'] == 2
    # No premature circuit opening: provider was invoked on all 4 cases.


def test_resume_rejects_incompatible_policy_model_and_limit(isolated_report, monkeypatch):
    reserved.run_cases('ai',limit=2,delay=0,diagnose_ai=lambda d,e:output(),sleep=lambda _:None)
    with pytest.raises(ValueError,match='incompatível'):
        reserved.run_cases('ai',limit=3,resume=True,diagnose_ai=lambda d,e:output())
    old=reserved.config
    monkeypatch.setattr(reserved,'config', SimpleNamespace(gemini_model='ANOTHER-MODEL'))
    with pytest.raises(ValueError,match='incompatível'):
        reserved.run_cases('ai',limit=2,resume=True,diagnose_ai=lambda d,e:output())
    monkeypatch.setattr(reserved, 'config', old)
    report=json.loads(isolated_report.read_text())
    report['policy_sha256_prefix']='0'*16
    isolated_report.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='incompatível'):
        reserved.run_cases('ai',limit=2,resume=True,diagnose_ai=lambda d,e:output())


def test_resume_legacy_v27_report_without_new_fields(isolated_report):
    report=reserved.run_cases('ai',limit=3,delay=0,
                              diagnose_ai=lambda d,e:output(),sleep=lambda _:None)
    prior=json.loads(isolated_report.read_text())
    prior.pop('target_case_count')
    prior.pop('run_status')
    prior['summary'].pop('pending_cases')
    # Legacy records with a provider failure were counted as errors and should be retried.
    prior['details'][1]['model_error']=True
    prior['details'][1]['error']='ServerError HTTP 503'
    prior['summary']['mode']='ai'
    isolated_report.write_text(json.dumps(prior))
    called=[]
    resumed=reserved.run_cases('ai',limit=3,delay=0,resume=True,
                              diagnose_ai=lambda d,e:(called.append(1),output())[1],sleep=lambda _:None)
    assert len(called)==1
    assert resumed['run_status']=='complete'
    assert resumed['summary']['answered_cases']==3


def test_no_api_in_offline_mode_and_accurate_available_denominator(isolated_report):
    def forbidden(*args,**kwargs):
        raise AssertionError('No external call allowed')
    report=reserved.run_cases('offline',limit=4,delay=0,diagnose_ai=forbidden,sleep=lambda _:None)
    assert report['run_status']=='complete'
    assert report['summary']['api_availability_pct'] is None
    assert report['summary']['api_errors']==0
    assert report['summary']['target_cases']==4
    with pytest.raises(ValueError,match='somente'):
        reserved.run_cases('offline',limit=4,resume=True,diagnose_ai=forbidden)


def test_keyboard_interrupt_saves_checkpoint(isolated_report):
    def interrupt(*args):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        reserved.run_cases('ai',limit=3,delay=0,diagnose_ai=interrupt,sleep=lambda _:None)
    report=json.loads(isolated_report.read_text())
    assert report['run_status']=='interrupted'
    assert report['summary']['pending_cases']==3


def test_docker_image_contains_release_version():
    root=Path(__file__).resolve().parents[1]
    assert 'COPY VERSION ./VERSION' in (root/'Dockerfile').read_text()
    assert (root/'VERSION').read_text().strip()=='2.8.0'
    assert policy_digest()  # Source policy is still present


def test_new_run_archives_previous_report(isolated_report):
    prior=reserved.run_cases('offline',limit=1,delay=0,sleep=lambda _:None)
    fresh=reserved.run_cases('offline',limit=2,delay=0,sleep=lambda _:None)
    archives=list(isolated_report.parent.glob('reserved_archive_*.json'))
    assert len(archives)==1
    assert json.loads(archives[0].read_text())['summary']['target_cases']==1
    assert fresh['summary']['target_cases']==2
    assert prior['details'][0]['case_id']=='RES-01'


def test_cli_file_lock_blocks_two_concurrent_benchmarks(isolated_report):
    with reserved.evaluation_lock():
        with pytest.raises(ValueError,match='Outra avaliação'):
            with reserved.evaluation_lock():
                pass
