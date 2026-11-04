# ResolveAI 2.8 — proteção contra API instável e retomada

## O problema observado

No teste reservado com 20 casos no Ubuntu, **16 casos não obtiveram resposta da API** devido a erros HTTP 503/504 e timeout. Somente quatro respostas foram recebidas; não é correto apresentar a taxa de acerto como se todos os 20 tivessem sido diagnosticados. O resultado mostra indisponibilidade do provedor na ocasião, não um problema de acesso ao site local.

A versão 2.8 separa **disponibilidade** (respostas válidas / casos efetivamente tentados), **acurácia entre respostas válidas** e **segurança após política**. Todos os números continuam restritos a exemplos sintéticos e nenhuma correção é executada durante essa bateria.

## Atualização a partir do ResolveAI 2.7

1. No terminal da **pasta 2.7**, execute `docker compose down` (sem `-v`).
2. Descompacte o pacote 2.8 em outra pasta e copie o `.env` da pasta 2.7 para `resolveai/.env` na versão 2.8. Não exponha a chave.
3. Na pasta interna `resolveai` da versão 2.8, execute `./scripts/start_docker.sh`.
4. Confira `docker compose ps` e abra <http://127.0.0.1:8501>.

O Dockerfile 2.8 inclui `COPY VERSION ./VERSION`, que evita o erro `/workspace/VERSION` da 2.7. Os volumes Docker `app_data` e `lab_data` são preservados enquanto o nome do projeto Compose permanecer igual. Não execute `docker compose down -v`.

## Retomar sem repetir respostas anteriores

**IMPORTANTE:** se você já tem o relatório Gemini da 2.7 (16 falhas e 4 respostas), **não execute um novo benchmark antes de retomar**. O relatório deve estar no mesmo volume Docker, ou precisará ser recuperado do backup.

```bash
docker compose exec -T app python -m scripts.reserved --mode ai --confirm-api-usage --limit 20 --resume
```

O programa:

- Confere se o modelo, o identificador do conjunto, a política e o limite são os mesmos. Não mistura resultados incompatíveis.
- Preserva cada diagnóstico que recebeu resposta válida na execução anterior. Somente casos que falharam ou nem foram iniciados são enviados novamente ao Gemini.
- Salva um relatório após cada caso, de modo que interrupções não descartem resultados anteriores.
- Se ocorrerem **duas falhas transitórias consecutivas** (por exemplo, HTTP 503/504 ou `ReadTimeout`), **pausa a bateria**, grava o estado e não faz mais chamadas até você optar por retomar.
- Para HTTP 429 ou erros não transitórios, pausa imediatamente. Nunca contorna limites de cota.
- Sugere uma pausa de dez minutos, mas **não faz processamento em segundo plano**, nem inicia uma nova avaliação automaticamente.
- Ao retomar, ainda pode haver novas tentativas de casos falhos. A autorização `--confirm-api-usage` é obrigatória a cada execução.

Se você não tiver um relatório anterior, inicie uma bateria pequena **somente quando desejar consumir cota Gemini**:

```bash
docker compose exec -T app python -m scripts.reserved --mode ai --confirm-api-usage --limit 5
```

Se iniciar um lote novo sem `--resume`, o relatório antigo é arquivado em `/workspace/data/reserved_archive_*.json` para evitar perda acidental. Para preservar resultados do lote de 20 casos, prefira `--resume --limit 20`.

**Atenção ao limite:** uma bateria de cinco casos não pode ser retomada como uma de 20. Isso evita misturar subconjuntos diferentes. Erros de versão e política também impedem retomada incorreta.

## Teste sem consumir Gemini

```bash
docker compose exec -T app python -m scripts.reserved --mode offline --limit 20
```

Esse teste usa somente regras determinísticas e **substitui o relatório mais recente**, arquivando o anterior. Não execute antes de retomar seus dados Gemini se desejar manter a avaliação principal visível.

## Relatórios e interpretação

Na seção **Validação adicional**:

- **Disponibilidade API:** respostas / tentativas (ex.: 4/20 = 20%). Não inclui casos ainda não tentados.
- **Acertos do Gemini:** acertos / respostas válidas. Se o Gemini não respondeu, não se atribui um acerto.
- **Acertos após política:** decisões corretas / respostas válidas, após validação do sistema.
- **Erros de API:** casos que ficaram sem resposta na última tentativa.
- **Pendentes:** casos nunca iniciados **e** casos que precisam ser tentados novamente por falha de API.
- **Estado:** em andamento, pausado, interrompido ou concluído. Uma avaliação pausada não deve ser relatada como uma bateria finalizada.

A saída da CLI usa código de retorno **75** quando a avaliação não está concluída, para facilitar identificação por ferramentas automatizadas.

## Segurança, custo e limitações

- Não são executadas ações de reparo durante o benchmark.
- As chamadas com Gemini usam a configuração da sua `.env`. Elas consomem a cota disponível; o nível gratuito não gera cobrança enquanto você não tiver ativado faturamento.
- Logs de erros mostram apenas tipo e código HTTP, sem chave, URL interna, prompt ou corpo da resposta.
- O contêiner ainda depende da estabilidade da API e da rede. A proteção diminui chamadas desperdiçadas, **não elimina erros 503 ou 504**.
- O tempo limite do SDK é por requisição HTTP, não um prazo de execução absoluto para todo o processo Python.
- Não há retentativa automática futura e não há agendamento de tarefas.
- A bateria já foi utilizada em desenvolvimento e não deve ser descrita como validação independente, cega ou representativa de ambiente de produção.
