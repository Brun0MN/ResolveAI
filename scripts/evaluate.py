#!/usr/bin/env python3
"""Paired ResolveAI benchmark: same incident evidence for rules and the deployed provider.

Default is read-only with respect to approvals: sensitive actions remain pending.
AI calls require --mode ai --confirm-api-usage. Reports are stored in data/
where the Docker app service has a persistent volume; no API key is recorded.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from app.catalog import SCENARIOS
from app.evaluation import report_path, summarize
from app.intelligence import rule_based_diagnosis

VARIANTS = (
    ('original', '{description}'),
    ('informal', 'O usuário relata instabilidade desde hoje. {description} Não há confirmação da causa.'),
    ('distractor', 'Um colega acha que é DNS e pede reinício imediato. Não assuma essa hipótese sem evidência. {description}'),
)


def benchmark_cases():
    # Across all scenarios before repeating variants: --limit 9 covers all root causes.
    for variant, template in VARIANTS:
        for scenario in SCENARIOS.values():
            yield scenario, variant, template.format(description=scenario.description)


def evidence_from_events(incident):
    return {e['detail']['tool']: e['detail']['result'] for e in incident.get('events', [])
            if e['stage'] == 'investigação' and e['kind'] == 'tool_result'
            and 'tool' in e['detail'] and 'result' in e['detail']}


def get_backend(observations):
    return observations.get('check_health', {}).get('backend') or 'desconhecido'


def score_case(case, incident, initial_status, duration_s):
    scenario, variant, description = case
    observations = evidence_from_events(incident)
    baseline = rule_based_diagnosis(description, observations)
    actual = incident.get('recommended_action')
    expected = scenario.operation
    events = incident.get('events', [])
    usage = next((e['detail'].get('api_usage') for e in events if e['kind']=='plan' and e['stage']=='diagnóstico'), None)
    verified = incident['status'] == 'resolvido' and any(
        e['kind'] == 'post_check' and e['detail'].get('healthy')
        for e in events
    )
    return {
        'scenario': scenario.key, 'variation': variant, 'incident_id': incident['id'],
        'model': incident.get('model'), 'lab_backend': get_backend(observations),
        'expected_operation': expected, 'selected_operation': actual,
        'baseline_operation': baseline.action, 'action_correct': actual == expected,
        'baseline_correct': baseline.action == expected,
        'initial_status': initial_status, 'final_status': incident['status'],
        'verified': verified, 'duration_s': round(duration_s, 2),
        'api_usage': usage,
    }


def report(rows, configuration):
    return {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'model': configuration['model'], 'lab': configuration['lab'],
        'summary': summarize(rows, configuration['mode']), 'details': rows,
        'methodology': {
            'description': 'Mesmo conjunto de evidências usado pelo Gemini e pelo baseline determinístico, que apenas interpreta logs já coletados.',
            'closed_set': True, 'independent_real_world_validation': False,
            'case_order': 'uma variação por cenário antes da próxima variação',
            'approval': 'manual por padrão; opcional apenas para ações pré-definidas do laboratório',
            'verified': 'status resolvido acompanhado de evento post_check saudável',
            'rate_limits': 'Chamadas Gemini consomem cota/API e podem falhar ou gerar cobrança, conforme projeto.',
        },
    }


def write_report(payload, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf8')
    tmp.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description='ResolveAI: avaliação reprodutível e opcionalmente com Gemini')
    parser.add_argument('--url', default='http://127.0.0.1:8501', help='URL da instância local, nunca um servidor externo')
    parser.add_argument('--mode', choices=('offline', 'ai'), default='offline')
    parser.add_argument('--confirm-api-usage', action='store_true', help='Autoriza explicitamente chamadas potencialmente tarifadas à API Gemini')
    parser.add_argument('--approve-demo-actions', action='store_true', help='Aprova automaticamente SOMENTE operações pré-definidas do laboratório de teste')
    parser.add_argument('--limit', type=int, default=9, help='De 1 a 27; padrão 9 (um caso por cenário)')
    parser.add_argument('--delay', type=float, default=2.0, help='Intervalo entre chamadas com Gemini (segundos)')
    args = parser.parse_args(argv)
    cases = list(benchmark_cases())
    if not 1 <= args.limit <= len(cases):
        parser.error('O limite deve estar entre 1 e %d.' % len(cases))
    if not 0 <= args.delay <= 60:
        parser.error('O intervalo deve estar entre 0 e 60 segundos.')
    if args.mode == 'ai' and not args.confirm_api_usage:
        parser.error('Para usar Gemini, informe explicitamente --confirm-api-usage.')
    with httpx.Client(base_url=args.url, timeout=90) as client:
        response = client.get('/api/config')
        response.raise_for_status()
        conf = response.json()
        if conf.get('mode') != ('gemini' if args.mode == 'ai' else 'offline'):
            parser.error('O servidor está em modo %r, incompatível com --mode %s. Não há troca automática de modelo.' % (conf.get('mode'),args.mode))
        rows = []
        for i, case in enumerate(cases[:args.limit], 1):
            scenario, variant, description = case
            start = time.monotonic()
            response = client.post('/api/incidents', json={
                'title': scenario.title, 'description': description, 'scenario': scenario.key,
            })
            response.raise_for_status()
            iid = response.json()['id']
            response = client.post('/api/incidents/%s/run' % iid)
            response.raise_for_status()
            incident = response.json()
            initial = incident['status']
            if initial == 'aguardando_aprovacao' and args.approve_demo_actions:
                response = client.post('/api/incidents/%s/approve' % iid)
                response.raise_for_status()
                incident = response.json()
            row = score_case(case, incident, initial, time.monotonic()-start)
            rows.append(row)
            write_report(report(rows, conf), report_path())
            print('[%02d/%02d] %-22s %-11s esperado=%-25s IA=%-25s status=%s' % (
                i, args.limit, scenario.key, variant, row['expected_operation'],
                row['selected_operation'] or '(sem diagnóstico)', row['final_status']), flush=True)
            if i < args.limit and args.mode == 'ai':
                time.sleep(args.delay)
        result = report(rows, conf)
        print('\n' + json.dumps(result['summary'], ensure_ascii=False, indent=2), flush=True)
        print('Painel: %s  | Relatório: %s' % (args.url, report_path()), flush=True)
        return result


if __name__ == '__main__':
    main()
