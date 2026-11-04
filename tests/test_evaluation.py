import json
from types import SimpleNamespace
from app import storage, evaluation
from app.catalog import SCENARIOS
from app.intelligence import rule_based_diagnosis
from scripts.evaluate import benchmark_cases, score_case


def test_unknown_scenario_escalates_without_operation(environment):
    agent, _ = environment
    case = SCENARIOS['unknown_failure']
    iid = agent.triage.create(case.title,case.description,case.key)
    result = agent.run(iid)
    assert result['status'] == 'escalado'
    assert result['recommended_action'] == 'escalate'
    assert not any(e['kind']=='operation' for e in result['events'])


def test_evaluation_scenario_coverage():
    cases=list(benchmark_cases())
    assert len(cases)==len(SCENARIOS)*3
    assert len({case.key for case, _, _ in cases[:len(SCENARIOS)]})==len(SCENARIOS)
    assert cases[0][1]=='original'
    assert cases[-1][1]=='distractor'


def test_paired_scoring_from_same_evidence(environment):
    agent,_=environment
    case=SCENARIOS['web_stopped']
    iid=agent.triage.create(case.title,case.description,case.key)
    incident=agent.run(iid)
    row=score_case((case,'original',case.description),incident,incident['status'],0.1)
    assert row['action_correct'] is True
    assert row['baseline_correct'] is True
    assert row['verified'] is True
    assert row['lab_backend']=='emulated'


def test_report_summary_and_missing_file(tmp_path,monkeypatch):
    monkeypatch.setattr(evaluation,'config',SimpleNamespace(database_path=str(tmp_path/'db.sqlite3')))
    result=evaluation.latest_evaluation()
    assert not result['available']
    cases=[{'expected_operation':'restart_demo_web', 'action_correct':True,'baseline_correct':True,
            'verified':True,'selected_operation':'restart_demo_web','final_status':'resolvido',
            'model':'gemini:test','duration_s':1,'lab_backend':'process-isolated'},
           {'expected_operation':'escalate','action_correct':True,'baseline_correct':True,
            'verified':False,'selected_operation':'escalate','final_status':'escalado',
            'model':'gemini:test','duration_s':1,'lab_backend':'emulated'}]
    stats=evaluation.summarize(cases,'gemini')
    assert stats['decision_accuracy_pct']==100
    assert stats['verified_resolution_pct']==100
    assert stats['correct_escalation_pct']==100
    path=evaluation.report_path()
    path.write_text(json.dumps({'summary':stats,'details':cases}))
    assert evaluation.latest_evaluation()['available']


def test_incorrect_action_is_counted():
    stats=evaluation.summarize([{'expected_operation':'restart_demo_web','selected_operation':'restore_demo_dns',
       'action_correct':False,'baseline_correct':True,'verified':False,
       'final_status':'escalado','model':'gemini:x','duration_s':2,'lab_backend':'emulated'}],'gemini')
    assert stats['decision_accuracy_pct']==0
    assert stats['baseline_accuracy_pct']==100
    assert stats['verified_resolution_pct']==0
