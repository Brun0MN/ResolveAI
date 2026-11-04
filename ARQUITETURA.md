# Arquitetura técnica — ResolveAI 2.8

## Objetivo

Demonstrar um fluxo controlado de investigação e recuperação de incidentes de TI. Um modelo de linguagem interpreta evidências e propõe ações, **mas não decide sozinho o que pode ser executado**.

## Fluxo e papéis

| Etapa | Implementação | Usa LLM? |
|---|---|---|
| Triagem | `TriageAgent` registra incidente e cria cenário isolado | Não |
| Investigação | `InvestigationAgent` coleta ferramentas predefinidas: saúde, logs, métricas, configurações | Não |
| Diagnóstico | `app/intelligence.py` solicita decisão estruturada ao Gemini ou usa baseline offline | **Sim, somente no modo Gemini** |
| Política | `app/policy.py` valida evidências e operação autorizada | Não |
| Resolução | `ResolutionAgent` solicita operação permitida ao laboratório | Não |
| Verificação | Novo teste de saúde e registro em SQLite | Não |

A solução **não usa quatro agentes autônomos LLM** e **não usa RAG** na versão 2.8. Esta escolha reduz complexidade e consumo de API, mas também limita a capacidade de consultar documentação específica e planejar investigações abertas.

## Componentes

- `app/main.py`: endpoints FastAPI e interface acessível somente via `127.0.0.1:8501` no Compose fornecido.
- `app/workflow.py`: máquina de estados de incidentes e auditoria.
- `app/intelligence.py`: diagnóstico Gemini, formatação de resultados, tentativas e classificação de falhas da API.
- `app/policy.py`: autorização independente com evidências atuais; **não** confiar em uma frase de log como instrução operacional.
- `app/catalog.py`: cenários sintéticos, ferramentas e lista limitada de operações.
- `lab/` e `real_lab/`: laboratório controlado e processos de teste.
- `app/storage.py`: persistência dos incidentes/eventos em SQLite.
- `scripts/reserved.py`: avaliação *somente diagnóstico*, checkpoints, retomada, pausa em falhas repetidas e relatórios.

## Por que verificar depois de agir?

Uma resposta do modelo pode estar linguisticamente convincente e ainda ser errada. Uma ação aprovada não encerra automaticamente o incidente: o laboratório é consultado outra vez. **HTTP 200 no alvo de demonstração** significa que o serviço de teste voltou a responder, não que a mesma ação funcionaria em uma infraestrutura de produção.

## Disponibilidade da API e circuit breaker

O cliente faz até três tentativas totais para erros transitórios, com sinais de progresso e timeout por requisição. Na avaliação em lote, o programa salva resultados por caso, evita sobrescrever registros compatíveis e pode pausar quando há falhas consecutivas. O painel distingue: (a) quantas respostas chegaram; (b) o acerto entre respostas; (c) a decisão após a política. Tentativas podem falhar mesmo quando o relatório final fica completo.

## Extensões futuras, não implementadas

1. **RAG:** recuperar procedimentos versionados e citar a origem do documento no diagnóstico.
2. **Investigações com ferramentas escolhidas dinamicamente:** somente leitura primeiro, com política de acesso.
3. **Monitoramento proativo:** receber eventos e métricas de sistemas autorizados.
4. **Autenticação e RBAC:** papéis, segregação de funções e identidade do aprovador.
5. **Testes externos:** falhas não vistas, ambientes diversos e revisão independente de segurança.

Extensões só devem ser adotadas se melhorarem métricas relevantes, não apenas por acrescentarem agentes.
