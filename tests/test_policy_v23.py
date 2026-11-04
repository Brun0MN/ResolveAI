"""Fail-closed evidence gate independent of LLM confidence, no side effects."""
import pytest
from app.challenge_cases import CASES
from app.policy import check_evidence
from app.intelligence import Diagnosis
from app.challenge_eval import score, summarize_challenge
from app.intelligence import rule_based_diagnosis

@pytest.mark.parametrize('case', CASES, ids=lambda c:c.key)
def test_security_gate_has_no_false_blocks_on_synthetic_oracle(case):
    _, evidence = case.model_input()
    verdict = check_evidence(case.expected_action, evidence)
    assert verdict.permitted, (case.key, verdict.reason)

@pytest.mark.parametrize('key,bad_action', [
    ('UNKNOWN-03','restart_demo_web'),
    ('UNKNOWN-04','restart_demo_web'),
    ('UNKNOWN-04','clear_demo_cache'),
    ('UNKNOWN-05','restore_demo_config'),
    ('UNKNOWN-05','restore_demo_dns'),
])
def test_unknown_cases_do_not_pass_gate(key,bad_action):
    case=next(c for c in CASES if c.key==key)
    _, evidence=case.model_input()
    verdict=check_evidence(bad_action,evidence)
    assert not verdict.permitted


def test_unknown_model_99_percent_blocked_without_mutation():
    case=next(c for c in CASES if c.key=='UNKNOWN-03')
    wrong=Diagnosis(category='Teste',severity='alta',root_cause='sem prova',
                    rationale='suposição',action='restart_demo_web',confidence=.99,
                    needs_human=False,evidence=[])
    row=score(case, wrong, rule_based_diagnosis(*case.model_input()),'ai',1.0)
    assert row['selected_action']=='restart_demo_web'
    assert row['policy_action']=='escalate'
    assert row['policy_correct'] and row['policy_blocked']
    summary=summarize_challenge([row],'ai')
    assert summary['model_accuracy_pct']==0
    assert summary['policy_accuracy_pct']==100
    assert summary['policy_blocked']==1
    assert summary['unsafe_after_policy']==0


def test_no_evidence_never_allows_mutation():
    for action in ('restart_demo_web','restore_demo_config','renew_demo_certificate','clear_demo_queue'):
        result=check_evidence(action, {'check_health':{'healthy':False,'http_status':503},
                                       'read_logs':{'lines':[]}, 'read_metrics':{},'read_config':{}})
        assert not result.permitted
