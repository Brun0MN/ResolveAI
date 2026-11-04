# Avaliação e evidências — ResolveAI 2.8

## Resumo confirmado pela execução do operador

Em 04/11/2026, o operador executou a bateria de **20 casos sintéticos RES-01 a RES-20**. Houve uma primeira execução com muitas falhas HTTP 503/504. Depois de reparar os metadados de um relatório parcial e usar a opção `--resume`, o terminal mostrou:

```text
Retomada: preservadas 1 respostas; 19 casos pendentes ou com erro.
Resumo: 20 respostas válidas / 20 casos previstos | 0 erros no relatório | 0 pendentes | estado: complete
Acerto entre respostas: 75.0 % modelo; 100.0 % política.
```

O processo retomado encontrou um HTTP 503 em uma tentativa e obteve uma resposta na tentativa seguinte. Os cinco casos em que a decisão bruta do Gemini divergiu do gabarito foram encaminhados pela política.

| Indicador | Quantidade | O que mede |
|---|---:|---|
| Respostas finais válidas | 20/20 | Casos com saída válida após retomada; **não** uptime da API |
| Acertos da decisão do Gemini | 15/20 (75%) | Comparação da proposta bruta com a ação esperada |
| Acertos após a política | 20/20 (100%) | Concordância da decisão autorizada/encaminhada com o gabarito |
| Falhas finais registradas | 0 | Falhas no relatório concluído, não no histórico de tentativas |

**Fonte:** saída de terminal e capturas compartilhadas durante a validação. O arquivo bruto `/workspace/data/reserved_latest.json` não foi disponibilizado para esta preparação do portfólio; **não foi inventado nem incluído um JSON de resultados reais**. Para anexar evidência primária, o operador pode exportar esse arquivo do próprio Ubuntu após revisar seu conteúdo.

## Desenho do teste

- 20 casos criados especificamente para a avaliação; incluem falhas com evidência clara, insuficiente, histórica e instruções maliciosas em logs.
- Gabarito definido previamente pelo projeto e não enviado ao modelo.
- Comparação entre resposta bruta do modelo e resultado da política.
- O benchmark é **somente de diagnóstico**: não executa correções no laboratório durante a bateria.
- Parte dos testes e critérios do projeto foram elaborados pelo mesmo autor/desenvolvedor. A bateria foi inicialmente congelada, mas passou a ser usada como referência de desenvolvimento e **não deve ser chamada de avaliação externa independente**.

## Limitações

**Não confundir:**

- **Acerto pós-política (100%)** com **100% de incidentes resolvidos**. Encaminhar corretamente conta como decisão correta no gabarito, não como reparo automático.
- **Disponibilidade final (20/20)** com ausência de indisponibilidade. Foram observadas falhas HTTP 503/504 e esperas por resposta em execuções anteriores.
- **Teste de laboratório** com desempenho em produção. Há apenas algumas classes de falhas, ações predefinidas e serviços de teste.
- **120 testes Python automatizados aprovados** com validação operacional em ambientes diversos.

## Como reportar os números a um recrutador

> Em uma bateria de 20 incidentes sintéticos, o Gemini escolheu a decisão esperada em 15 casos (75%). Uma política independente de segurança encaminhou os cinco casos em que a sugestão não tinha sustentação suficiente, alcançando 20/20 decisões consistentes com o gabarito. O benchmark não realizou reparos, e a estabilidade da API precisou ser tratada com tentativas, checkpoints e retomada.

Recomenda-se apresentar junto o limite do conjunto sintético e uma demonstração de um serviço de teste recuperado com verificação de saúde.

## Próximas medições desejáveis

- Disponibilidade da API por período e por tentativa, não só por resposta final.
- Taxa real de recuperação por tipo de falha e custo operacional por incidente.
- Falsos bloqueios da política e decisões inseguras não bloqueadas.
- Avaliação externa de falhas não vistas e comparação justa sem/ com RAG caso seja implementado.
