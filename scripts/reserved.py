#!/usr/bin/env python3
"""Read-only evaluation with resumable checkpoints and a provider circuit breaker.

The benchmark never operates the demo lab. AI usage always requires opt-in.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time
import fcntl

from app.config import config
from app.reserved_cases import CASES
from app.reserved_eval import save, report_path
from app.holdout_eval import score, summary
from app.intelligence import (
    diagnostic_progress, gemini_diagnosis, public_provider_error,
    provider_error_code, rule_based_diagnosis, _is_transient_server_error,
)
from app.release import policy_digest, version


SET_ID = 'reserved-author-defined-2026-11-v1'


def now_utc():
    return datetime.now(timezone.utc)


def fixture_hash():
    # The oracle must not be included in the model input.
    canonical = json.dumps([
        {'key': c.key, 'group': c.group, 'input': c.model_input(),
         'expected_action': c.expected_action, 'reason': c.explanation}
        for c in CASES], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _pending(target, row_map):
    return [c for c in target if c.key not in row_map or row_map[c.key].get('model_error')]


def build_report(rows, mode, *, target=None, status='complete', pause_reason=None,
                 started=None, retry_after=None, previous_error_count=0):
    """Separate attempted, answered, failed and not-yet-attempted cases."""
    target = list(target if target is not None else CASES[:len(rows)])
    stats = summary(rows, mode)
    stats.update({
        'version': version(), 'set': SET_ID,
        'target_cases': len(target), 'evaluated_cases': len(rows),
        'pending_cases': len(_pending(target, {r['case_id']: r for r in rows})),
        'api_availability_pct': (
            round(100 * stats['answered_cases'] / len(rows), 1)
            if mode == 'ai' and rows else None
        ),
        'previous_error_count': previous_error_count,
    })
    return {
        'timestamp_utc': now_utc().isoformat(timespec='seconds'),
        'started_utc': started or now_utc().isoformat(timespec='seconds'),
        'model': config.gemini_model if mode == 'ai' else 'Regras offline (sem IA)',
        'policy_sha256_prefix': policy_digest(),
        'fixture_sha256': fixture_hash(),
        'target_case_count': len(target),
        'run_status': status,
        'pause_reason': pause_reason,
        'suggested_retry_utc': retry_after,
        'summary': stats,
        'details': rows,
        'methodology': {
            'data_origin': '20 casos sintéticos autorais; conjunto de regressão após os testes da v2.7.',
            'oracle': 'Ação esperada e justificativa não são enviadas ao Gemini.',
            'exposure': 'Não é auditoria independente nem avaliação de produção.',
            'security': 'Somente leitura. Nenhuma correção ou chamada ao laboratório.',
            'limits': 'Disponibilidade = respostas / casos tentados. Acurácia = acertos / respostas válidas; sem resposta não é acerto.',
            'resume': 'Retomada reaproveita respostas válidas, mas tenta novamente falhas da API; exige confirmação de consumo.',
            'quota': 'Modo IA usa API; modo offline não gera chamadas Gemini.',
        },
    }


def load_resume(target, mode):
    path = report_path()
    try:
        if path.stat().st_size > 1_000_000:
            raise ValueError('Relatório de retomada muito grande')
        previous = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise ValueError('Nenhum relatório anterior para retomar. Execute sem --resume.') from exc
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError('Relatório anterior ilegível. Preserve-o antes de reiniciar.') from exc
    if not isinstance(previous, dict) or not isinstance(previous.get('summary'), dict):
        raise ValueError('Formato inválido de relatório anterior')
    conditions = [
        previous.get('fixture_sha256') == fixture_hash(),
        previous.get('policy_sha256_prefix') == policy_digest(),
        previous.get('model') == (config.gemini_model if mode == 'ai' else 'Regras offline (sem IA)'),
        previous['summary'].get('mode') == mode,
        previous.get('target_case_count', len(previous.get('details', []))) == len(target),
        isinstance(previous.get('details'), list),
    ]
    if not all(conditions):
        raise ValueError('Relatório incompatível (modelo, política, casos, modo ou limite); não misturar resultados.')
    ids = [c.key for c in target]
    seen = set()
    row_map = {}
    for row in previous['details']:
        if not isinstance(row, dict) or row.get('case_id') not in ids or row['case_id'] in seen:
            raise ValueError('Relatório anterior contém casos inválidos ou duplicados')
        seen.add(row['case_id'])
        row_map[row['case_id']] = row
    return row_map, previous.get('started_utc', previous.get('timestamp_utc'))


@contextmanager
def evaluation_lock():
    """Prevent two CLI benchmark processes from overwriting the same checkpoint."""
    path = report_path().with_suffix('.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+', encoding='utf-8') as lockfile:
        try:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Outra avaliação está em execução nesta instalação.') from exc
        try:
            yield
        finally:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)


def archive_previous_report():
    """Starting a new run never irreversibly overwrites the last JSON report."""
    source = report_path()
    if source.is_file():
        stamp = now_utc().strftime('%Y%m%d_%H%M%S_%f')
        backup = source.with_name(f'reserved_archive_{stamp}.json')
        shutil.copy2(source, backup)
        return backup
    return None


def _error_is_transient(error):
    return _is_transient_server_error(error)


def _pause_reason(error):
    code = provider_error_code(error)
    if code == 429:
        return 'limite_de_requisicoes'
    if _error_is_transient(error):
        return 'servico_temporariamente_indisponivel'
    return 'erro_nao_transitorio'


def run_cases(mode='offline', limit=None, delay=2., diagnose_ai=gemini_diagnosis,
              sleep=time.sleep, *, resume=False, circuit_threshold=2, cooldown_minutes=10):
    if limit is None:
        limit = len(CASES)
    if not isinstance(limit, int) or not 1 <= limit <= len(CASES):
        raise ValueError('Limite inválido')
    if mode not in ('offline', 'ai'):
        raise ValueError('Modo inválido')
    if resume and mode != 'ai':
        raise ValueError('Retomada somente para a execução real com IA')
    if not isinstance(circuit_threshold, int) or not 1 <= circuit_threshold <= 10:
        raise ValueError('Limiar de falhas inválido')
    if not 0 <= cooldown_minutes <= 240:
        raise ValueError('Intervalo de espera inválido')
    target = CASES[:limit]
    row_map, started = load_resume(target, mode) if resume else ({}, None)
    if not resume:
        archive_previous_report()
    old_errors = sum(bool(r.get('model_error')) for r in row_map.values())
    if resume:
        print(f'Retomada: preservadas {len(row_map)-old_errors} respostas; '
              f'{len(_pending(target,row_map))} casos pendentes ou com erro.', flush=True)
    started = started or now_utc().isoformat(timespec='seconds')

    def checkpoint(status, reason=None):
        rows = [row_map[c.key] for c in target if c.key in row_map]
        retry_after = ((now_utc() + timedelta(minutes=cooldown_minutes)).isoformat(timespec='seconds')
                       if status == 'paused_api' else None)
        report = build_report(rows, mode, target=target, status=status,
                              pause_reason=reason, started=started,
                              retry_after=retry_after, previous_error_count=old_errors)
        save(report)
        return report

    report = checkpoint('running')
    consecutive_transient_failures = 0
    try:
        pending = _pending(target, row_map)
        for i, case in enumerate(pending, 1):
            description, observation = case.model_input()
            baseline = rule_based_diagnosis(description, observation)
            response = None
            error = None
            caught = None
            started_case = time.monotonic()
            if mode == 'ai':
                print(f'[{i:02}/{len(pending):02}] {case.key}: iniciando Gemini...', flush=True)
                try:
                    with diagnostic_progress(lambda info: print('  ' + info, flush=True)):
                        response = diagnose_ai(description, observation)
                    consecutive_transient_failures = 0
                except Exception as exc:
                    caught = exc
                    error = public_provider_error(exc)
                    if _error_is_transient(exc):
                        consecutive_transient_failures += 1
                    else:
                        consecutive_transient_failures = 0
            else:
                response = baseline
            row = score(case, response, baseline, mode, time.monotonic() - started_case, error)
            row_map[case.key] = row
            report = checkpoint('running')
            print(f'[{i:02}/{len(pending):02}] {case.key}: '
                  f'modelo={row["selected_action"] or "SEM RESPOSTA"} '
                  f'política={row["policy_action"] or "SEM RESPOSTA"}'
                  + (f' erro={error}' if error else ''), flush=True)
            if caught is not None and (not _error_is_transient(caught) or
                                       consecutive_transient_failures >= circuit_threshold):
                reason = _pause_reason(caught)
                report = checkpoint('paused_api', reason)
                print('Circuito aberto: API instável ou indisponível. '
                      'Avaliação pausada sem novas chamadas. '
                      'Use --resume quando desejar tentar novamente.', flush=True)
                return report
            if mode == 'ai' and i < len(pending):
                sleep(delay)
    except KeyboardInterrupt:
        checkpoint('interrupted', 'interrompido_pelo_usuario')
        print('Interrompido: resultados preservados. Para continuar, use --resume.', flush=True)
        raise
    return checkpoint('complete' if not _pending(target, row_map) else 'paused_api',
                      None if not _pending(target, row_map) else 'falhas_pendentes')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Avaliação sintética resumível, somente diagnóstico')
    parser.add_argument('--mode', choices=['offline', 'ai'], default='offline')
    parser.add_argument('--limit', type=int, default=len(CASES))
    parser.add_argument('--delay', type=float, default=2.)
    parser.add_argument('--confirm-api-usage', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Reutilizar acertos, repetir apenas falhas/pendentes')
    parser.add_argument('--circuit-threshold', type=int, default=2,
                        help='Pausar após N falhas transitórias consecutivas (padrão: 2)')
    parser.add_argument('--cooldown-minutes', type=int, default=10,
                        help='Intervalo recomendado antes da retomada (sem espera automática)')
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= len(CASES): parser.error('Limite inválido')
    if not 0 <= args.delay <= 60: parser.error('Delay inválido')
    if not 1 <= args.circuit_threshold <= 10: parser.error('Limiar inválido')
    if not 0 <= args.cooldown_minutes <= 240: parser.error('Intervalo inválido')
    if args.mode == 'ai' and not args.confirm_api_usage:
        parser.error('Uso de API exige --confirm-api-usage')
    if args.mode == 'ai' and not config.gemini_key:
        parser.error('GEMINI_API_KEY não configurada')
    if args.resume and args.mode != 'ai':
        parser.error('--resume exige --mode ai')
    try:
        with evaluation_lock():
            result = run_cases(args.mode, args.limit, args.delay,
                               resume=args.resume, circuit_threshold=args.circuit_threshold,
                               cooldown_minutes=args.cooldown_minutes)
    except ValueError as exc:
        parser.error(str(exc))
    s = result['summary']
    print('Resumo:', s['answered_cases'], 'respostas válidas /', s['target_cases'],
          'casos previstos |', s['api_errors'], 'erros no relatório |',
          s['pending_cases'], 'pendentes | estado:', result['run_status'], flush=True)
    print('Acerto entre respostas:', s['model_accuracy_when_answered_pct'], '% modelo;',
          s['policy_accuracy_when_answered_pct'], '% política.', flush=True)
    print('Relatório:', report_path(), flush=True)
    return result


if __name__ == '__main__':
    import sys
    result = main()
    if result['run_status'] != 'complete':
        sys.exit(75)  # EX_TEMPFAIL: not a successful complete benchmark
