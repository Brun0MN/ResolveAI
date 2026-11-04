#!/usr/bin/env python3
"""Offline/AI diagnostic robustness benchmark; never touches Docker lab actions.

Model input is solely synthetic description and observed evidence, not the oracle.
Using AI requires explicit consent and may consume Gemini quota or trigger billing.
"""
import argparse
from datetime import datetime, timezone
import time
from app.challenge_cases import CASES
from app.challenge_eval import save_challenge, score, summarize_challenge, challenge_path
from app.intelligence import rule_based_diagnosis, gemini_diagnosis
from app.config import config


def build_report(rows,mode):
    return {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'model':config.gemini_model if mode=='ai' else 'baseline de regras (SEM IA)',
        'summary': summarize_challenge(rows,mode), 'details':rows,
        'methodology': {
            'type':'read-only: somente decisões; não executa correções nem cria incidentes',
            'oracle_visibility':'A resposta esperada não aparece no prompt nem nas ferramentas recebidas pela IA.',
            'data_origin':'Exemplos fictícios e redigidos manualmente; avaliação não é independente nem representa produção.',
            'prompt_injection':'Mensagens adversárias estão dentro de linhas de logs marcadas como dados não confiáveis.',
            'baseline':'Regras de correspondência fixa da versão 2.1; não é um modelo de IA.',
            'policy':'Porta determinística independente do modelo; exige evidências atuais antes de permitir ação no laboratório. Mede decisões após bloqueio, sem executar nenhuma correção.',
            'cost':'Chamadas reais à Gemini são opcionais e precisam de consentimento explícito. Contagem de tokens pode estar incompleta.',
        },
    }


def run_cases(mode, limit, delay, diagnose_ai=gemini_diagnosis, sleep=time.sleep):
    rows=[]
    for idx,case in enumerate(CASES[:limit],1):
        description,observations=case.model_input()
        baseline=rule_based_diagnosis(description,observations)
        started=time.monotonic()
        response=None; error=None
        if mode=='ai':
            try:
                response=diagnose_ai(description,observations)
            except Exception as exc:
                # Do not save provider raw messages (might contain secrets).
                error=type(exc).__name__
        else:
            response=baseline
        row=score(case,response,baseline,mode,time.monotonic()-started,error)
        rows.append(row)
        save_challenge(build_report(rows,mode))
        status='OK' if row['correct'] else 'ERRO'
        print(f'[{idx:02}/{limit:02}] {case.key:<12} {status:<5} previsto={case.expected_action:<25} resposta={row["selected_action"] or "(sem resposta)"}',flush=True)
        if idx<limit and mode=='ai':
            sleep(delay)
    return build_report(rows,mode)


def main(argv=None):
    p=argparse.ArgumentParser(description='Teste de robustez sintético e somente diagnóstico (ResolveAI 2.3)')
    p.add_argument('--mode',choices=('offline','ai'),default='offline')
    p.add_argument('--confirm-api-usage',action='store_true',help='Autoriza chamadas à Gemini; podem consumir cota ou gerar cobrança.')
    p.add_argument('--limit',type=int,default=len(CASES))
    p.add_argument('--delay',type=float,default=2.0,help='Pausa entre chamadas pagas (0 a 60s)')
    args=p.parse_args(argv)
    if not 1<=args.limit<=len(CASES):
        p.error(f'--limit deve estar entre 1 e {len(CASES)}.')
    if not 0<=args.delay<=60:
        p.error('--delay deve estar entre 0 e 60 segundos.')
    if args.mode=='ai' and not args.confirm_api_usage:
        p.error('Para usar a API Gemini, inclua --confirm-api-usage.')
    if args.mode=='ai' and not config.gemini_key:
        p.error('GEMINI_API_KEY não configurada; nenhuma chamada realizada.')
    result=run_cases(args.mode,args.limit,args.delay)
    s=result['summary']
    print(f'\nDecisões: {s["model_accuracy_pct"]}% | Regras: {s["baseline_accuracy_pct"]}% | '
          f'Falhas de API: {s["api_errors"]} | Casos adversários: {s["injection_cases"]}\n'
          f'Relatório: {challenge_path()}',flush=True)
    return result

if __name__=='__main__':
    main()
