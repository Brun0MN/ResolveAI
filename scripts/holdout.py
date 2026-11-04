#!/usr/bin/env python3
"""Read-only held-out diagnostic benchmark. AI must be explicitly requested."""
import argparse
from datetime import datetime, timezone
import time
from app.config import config
from app.holdout_cases import CASES
from app.holdout_eval import score, summary, save, report_path
from app.intelligence import gemini_diagnosis, rule_based_diagnosis, public_provider_error, diagnostic_progress
from app.release import policy_digest, version



def report(rows, mode):
    return {
        'timestamp_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'model':config.gemini_model if mode=='ai' else 'Regras determinísticas (sem IA)',
        'policy_sha256_prefix':policy_digest(),
        'summary':summary(rows,mode),'details':rows,
        'methodology':{
            'scope':'28 incidentes sintéticos agora REVISADOS no desenvolvimento v2.5. Avaliação de regressão; não é mais holdout independente.',
            'policy_freeze':'Política revisada em v2.5 usando observações dos casos. Este conjunto não é independente; o hash identifica a política testada.',
            'oracle':'Gabaritos e nomes dos casos são usados apenas para pontuação. Não entram na requisição da IA.',
            'limitations':'Conjunto sintético autoral, revisado após observar resultados. Não prova generalização nem confiabilidade em produção.',
            'scores':'Falha da API conta como erro, mas também exibimos taxa condicional às respostas válidas. Acurácia pós-política não equivale à acurácia do modelo.',
            'safety':'Somente leitura. Nenhuma ação é executada sobre contêineres, arquivos da aplicação ou host.',
            'cost':'Uso de Gemini requer --mode ai --confirm-api-usage e pode consumir quota. Sem flags, o modo é gratuito offline.',
        }
    }


def run_cases(mode='offline',limit=None,delay=2.0,diagnose_ai=gemini_diagnosis,sleep=time.sleep):
    if limit is None:limit=len(CASES)
    if not isinstance(limit,int) or not 1<=limit<=len(CASES):
        raise ValueError('Limite fora dos casos disponíveis')
    if mode not in ('offline','ai'):
        raise ValueError('Modo inválido')
    rows=[]
    for idx,case in enumerate(CASES[:limit],1):
        desc,obs=case.model_input()
        baseline=rule_based_diagnosis(desc,obs)
        started=time.monotonic()
        error=None;response=None
        if mode=='ai':
            print(f'[{idx:02}/{limit:02}] {case.key}: iniciando diagnóstico Gemini...', flush=True)
            try:
                with diagnostic_progress(lambda msg: print(f'  {msg}', flush=True)):
                    response=diagnose_ai(desc,obs)
            except Exception as ex:
                error=public_provider_error(ex)
        else:response=baseline
        row=score(case,response,baseline,mode,time.monotonic()-started,error)
        rows.append(row)
        save(report(rows,mode))
        print(f'[{idx:02}/{limit:02}] {case.key} resposta={row["selected_action"] or "SEM RESPOSTA"} '
              f'politica={row["policy_action"] or "SEM RESPOSTA"}'
              + (f' erro={error}' if error else ''),flush=True)
        if mode=='ai' and idx<limit:sleep(delay)
    return report(rows,mode)


def main(argv=None):
    p=argparse.ArgumentParser(description='ResolveAI: avaliação de regressão, somente leitura')
    p.add_argument('--mode',choices=['offline','ai'],default='offline')
    p.add_argument('--confirm-api-usage',action='store_true',help='Permite chamadas reais ao Gemini; consomem quota e podem gerar custo em projeto pago')
    p.add_argument('--limit',type=int,default=len(CASES))
    p.add_argument('--delay',type=float,default=2.0)
    args=p.parse_args(argv)
    if not 1<=args.limit<=len(CASES):p.error('Limite deve ser entre 1 e '+str(len(CASES)))
    if not 0<=args.delay<=60:p.error('Delay deve estar entre 0 e 60')
    if args.mode=='ai' and not args.confirm_api_usage:p.error('Para usar Gemini, especifique --confirm-api-usage')
    if args.mode=='ai' and not config.gemini_key:p.error('Configure GEMINI_API_KEY no .env, sem exibi-la no terminal')
    result=run_cases(mode=args.mode,limit=args.limit,delay=args.delay)
    print('\nResultados: Gemini/regras:',result['summary']['model_accuracy_pct'],
          '| Após política:',result['summary']['policy_accuracy_pct'],
          '| Ações inseguras não bloqueadas:',result['summary']['unsafe_actions_not_blocked'],
          '| Erros API:',result['summary']['api_errors'])
    print('Relatório:',report_path())
    return result


if __name__=='__main__':main()
