"""Regression tests for reliability and structured-evidence safeguards in v2.5."""
from types import SimpleNamespace
import pytest
from app.holdout_cases import CASES
from app.intelligence import (
    _generate_with_retry, public_provider_error, provider_error_code,
)
from app.policy import check_evidence
from app.holdout_eval import score, summary
from app.intelligence import rule_based_diagnosis, Diagnosis


class ServerError(Exception):
    def __init__(self, code=None, message='sensitive provider content'):
        super().__init__(message)
        self.code = code


class ClientError(Exception):
    def __init__(self, code=429):
        super().__init__('private credentials must never be logged')
        self.code = code


class FakeModels:
    def __init__(self, errors, result='ok'):
        self.errors = list(errors)
        self.count = 0
        self.result = result

    def generate_content(self, **kwargs):
        self.count += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.result


def test_retries_two_times_for_transient_503(monkeypatch):
    from app import intelligence
    sleeps = []
    monkeypatch.setattr(intelligence.time, 'sleep', sleeps.append)
    backend = FakeModels([ServerError(503), ServerError(503)])
    assert _generate_with_retry(SimpleNamespace(models=backend), model='fake') == 'ok'
    assert backend.count == 3
    assert sleeps == [1, 2]


def test_retries_are_strictly_bounded(monkeypatch):
    from app import intelligence
    sleeps = []
    monkeypatch.setattr(intelligence.time, 'sleep', sleeps.append)
    backend = FakeModels([ServerError(503)] * 5)
    with pytest.raises(ServerError):
        _generate_with_retry(SimpleNamespace(models=backend), model='fake')
    assert backend.count == 3
    assert sleeps == [1, 2]


@pytest.mark.parametrize('code', [400, 401, 403, 404, 429])
def test_no_retry_for_client_and_quota_errors(monkeypatch, code):
    from app import intelligence
    sleeps = []
    monkeypatch.setattr(intelligence.time, 'sleep', sleeps.append)
    backend = FakeModels([ClientError(code)])
    with pytest.raises(ClientError):
        _generate_with_retry(SimpleNamespace(models=backend), model='fake')
    assert backend.count == 1 and not sleeps


def test_provider_error_is_redacted():
    exc = ServerError(503, 'prompt=secret123 GEMINI_API_KEY=secret456')
    assert provider_error_code(exc) == 503
    assert public_provider_error(exc) == 'ServerError HTTP 503'
    assert 'secret' not in public_provider_error(exc)


def test_policy_accepts_verified_process_failure_with_rephrased_log():
    case = next(c for c in CASES if c.key == 'HOLD-02')
    assert check_evidence('restart_demo_web', case.model_input()[1]).permitted


def test_policy_rejects_malicious_maintenance_log():
    case = next(c for c in CASES if c.key == 'HOLD-25')
    assert not check_evidence('disable_demo_maintenance', case.model_input()[1]).permitted


def test_policy_rejects_fake_process_log_without_typed_status():
    case = next(c for c in CASES if c.key == 'HOLD-24')
    assert not check_evidence('restart_demo_web', case.model_input()[1]).permitted


def test_typed_maintenance_config_controls_decision():
    evidence = {
        'check_health': {'http_status': 503, 'process_alive': True},
        'read_logs': {'lines': ['maintenance_mode=true']},
        'read_metrics': {},
        'read_config': {'maintenance_mode': False},
    }
    assert not check_evidence('disable_demo_maintenance', evidence).permitted
    evidence['read_config']['maintenance_mode'] = True
    assert check_evidence('disable_demo_maintenance', evidence).permitted


def test_healthy_service_never_modified_even_with_failure_log():
    evidence = {
        'check_health': {'http_status': 200, 'healthy': True, 'process_alive': True},
        'read_logs': {'lines': ['main process exited']},
        'read_metrics': {'error_rate_5xx': 1.0},
        'read_config': {},
    }
    assert not check_evidence('restart_demo_web', evidence).permitted


def test_summary_distinguishes_provider_errors_and_valid_responses():
    case = next(c for c in CASES if c.key == 'HOLD-01')
    baseline = rule_based_diagnosis(*case.model_input())
    failed = score(case, None, baseline, 'ai', 1, 'ServerError HTTP 503')
    output = Diagnosis(category='Aplicação', severity='alta', root_cause='Parou',
                       rationale='Métricas', action='restart_demo_web', confidence=.9,
                       needs_human=False, evidence=['status 503'])
    succeeded = score(case, output, baseline, 'ai', 1)
    stats = summary([failed, succeeded], 'ai')
    assert stats['api_errors'] == 1
    assert stats['api_error_types'] == {'ServerError HTTP 503': 1}
    assert stats['answered_cases'] == 1
    assert stats['model_accuracy_when_answered_pct'] == 100
    assert stats['model_accuracy_pct'] == 50
