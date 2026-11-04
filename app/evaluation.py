"""Read-only evaluation reports and transparent metric calculations.

Operational incident KPIs and benchmark results intentionally remain separate.
No benchmark can be launched over HTTP (prevents accidental billable requests).
"""
import json
from pathlib import Path
from statistics import mean
from app.config import config


def report_path() -> Path:
    # Same persisted volume as SQLite inside Docker, never a user-supplied path.
    return Path(config.database_path).resolve().parent / 'evaluation_latest.json'


def summarize(rows, mode, version='2.1.0'):
    total = len(rows)
    actionable = [r for r in rows if r['expected_operation'] != 'escalate']
    unknowns = [r for r in rows if r['expected_operation'] == 'escalate']
    mean_duration = round(mean(r['duration_s'] for r in rows), 2) if rows else None
    def ratio(items, predicate):
        return round(100 * sum(bool(predicate(item)) for item in items) / len(items), 1) if items else None
    return {
        'version': version, 'mode': mode, 'cases': total,
        'actionable_cases': len(actionable), 'unknown_cases': len(unknowns),
        'decision_accuracy_pct': ratio(rows, lambda r: r['action_correct']),
        'baseline_accuracy_pct': ratio(rows, lambda r: r['baseline_correct']),
        'verified_resolution_pct': ratio(actionable, lambda r: r['verified']),
        'correct_escalation_pct': ratio(unknowns, lambda r: r['selected_operation'] == 'escalate' and r['final_status'] == 'escalado'),
        'mean_duration_s': mean_duration,
        'pending_approval': sum(r['final_status'] == 'aguardando_aprovacao' for r in rows),
        'api_errors': sum(r['model'] is None and mode == 'ai' for r in rows),
        'real_process_cases': sum(r['lab_backend'] == 'process-isolated' for r in rows),
        'emulated_cases': sum(r['lab_backend'] == 'emulated' for r in rows),
        'prompt_tokens': sum((r.get('api_usage') or {}).get('prompt_token_count') or 0 for r in rows),
        'generated_tokens': sum((r.get('api_usage') or {}).get('candidates_token_count') or 0 for r in rows),
        'total_tokens': sum((r.get('api_usage') or {}).get('total_token_count') or 0 for r in rows),
        'note': 'Conjunto fechado e sintético, não representa precisão em produção. Baseline usa assinaturas do próprio laboratório. Aprovações não são automáticas por padrão. Tokens de API são registrados quando a resposta da plataforma fornece metadados; custos em moeda não são calculados.',
    }


def latest_evaluation():
    path = report_path()
    if not path.is_file():
        return {'available': False, 'message': 'Nenhum benchmark executado nesta instalação. Consulte o README.'}
    try:
        if path.stat().st_size > 900_000:
            raise ValueError('Relatório acima do limite')
        data = json.loads(path.read_text(encoding='utf8'))
        if not isinstance(data, dict) or not isinstance(data.get('summary'), dict) or not isinstance(data.get('details'), list):
            raise ValueError('Formato inválido')
        return {'available': True, **data}
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return {'available': False, 'message': 'Relatório inválido ou indisponível.'}
