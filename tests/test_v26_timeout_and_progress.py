"""SDK retry multiplication, request timeout and terminal progress regressions."""
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app import intelligence
from app.holdout_cases import CASES
from scripts import holdout


class FakeServerError(Exception):
    def __init__(self, code=503):
        super().__init__('secret-key=THIS-MUST-STAY-HIDDEN')
        self.code = code


class FakeModels:
    def __init__(self, errors, result=None):
        self.errors = list(errors)
        self.result = result
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.result


def test_progress_always_reports_attempt_and_safe_error(monkeypatch):
    records = []
    sleeps = []
    monkeypatch.setattr(intelligence.time, 'sleep', sleeps.append)
    models = FakeModels([FakeServerError(503), FakeServerError(503)], result='ok')
    with intelligence.diagnostic_progress(records.append):
        assert intelligence._generate_with_retry(SimpleNamespace(models=models), model='fake') == 'ok'
    assert models.calls == 3
    assert sleeps == [1, 2]
    assert any('tentativa 1/3' in item for item in records)
    assert any('HTTP 503' in item for item in records)
    assert any('concluída' in item for item in records)
    assert not any('secret' in item for item in records)


def test_progress_context_is_reset_and_quota_does_not_retry(monkeypatch):
    records = []
    sleeps = []
    monkeypatch.setattr(intelligence.time, 'sleep', sleeps.append)
    with intelligence.diagnostic_progress(records.append):
        with pytest.raises(FakeServerError):
            intelligence._generate_with_retry(SimpleNamespace(models=FakeModels([FakeServerError(429)])))
    before = list(records)
    assert not sleeps
    with pytest.raises(FakeServerError):
        intelligence._generate_with_retry(SimpleNamespace(models=FakeModels([FakeServerError(429)])))
    assert records == before


def test_sdk_has_one_attempt_and_http_timeout(monkeypatch):
    captured = {}
    fake_genai = ModuleType('google.genai')
    fake_types = ModuleType('google.genai.types')

    class HttpRetryOptions:
        def __init__(self, attempts): self.attempts = attempts

    class HttpOptions:
        def __init__(self, timeout, retry_options):
            self.timeout = timeout
            self.retry_options = retry_options

    class Client:
        def __init__(self, api_key, http_options):
            captured['api_key'] = api_key
            captured['options'] = http_options
            self.models = FakeModels([], SimpleNamespace(
                parsed=None,
                text='{"category":"Aplicação","severity":"alta","root_cause":"teste","rationale":"teste","action":"escalate","confidence":0.6,"needs_human":true,"evidence":[]}',
                usage_metadata=None,
            ))
            captured['client'] = self
            self.closed = False

        def close(self): self.closed = True

    fake_genai.Client = Client
    fake_types.HttpOptions = HttpOptions
    fake_types.HttpRetryOptions = HttpRetryOptions
    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, 'google.genai', fake_genai)
    monkeypatch.setitem(sys.modules, 'google.genai.types', fake_types)
    monkeypatch.setattr(intelligence, 'config', SimpleNamespace(
        gemini_key='TEST-KEY', gemini_model='fake-model', gemini_request_timeout_s=20,
    ))

    result = intelligence.gemini_diagnosis('teste', {'check_health': {'healthy': False}})
    assert result.action == 'escalate'
    assert captured['options'].timeout == 20_000
    assert captured['options'].retry_options.attempts == 1
    assert captured['client'].closed


def test_holdout_continues_after_provider_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(holdout, 'save', lambda *_: None)
    monkeypatch.setattr(holdout, 'report_path', lambda: tmp_path / 'report.json')
    counter = {'n': 0}

    def provider(_description, _evidence):
        counter['n'] += 1
        if counter['n'] == 1:
            raise FakeServerError(503)
        from app.intelligence import rule_based_diagnosis
        return rule_based_diagnosis(_description, _evidence)

    result = holdout.run_cases(mode='ai', limit=2, diagnose_ai=provider, sleep=lambda *_: None)
    output = capsys.readouterr().out
    assert counter['n'] == 2
    assert 'iniciando diagnóstico' in output
    assert 'ServerError HTTP 503' in output
    assert result['summary']['api_errors'] == 1
    assert result['summary']['cases'] == 2
    assert 'secret' not in output
