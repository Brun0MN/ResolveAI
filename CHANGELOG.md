## 2.8.0 — Disponibilidade, pausa e retomada (2026-11-04)

- Circuit breaker no benchmark reservado: pausa após duas falhas transitórias consecutivas ou imediatamente após erro de cota/não transitório. Não executa chamadas em segundo plano.
- `--resume` retoma relatórios compatíveis, inclusive os produzidos pela 2.7, sem repetir respostas válidas.
- Checkpoints após cada caso e arquivos de backup ao iniciar uma bateria nova; bloqueio contra duas CLIs simultâneas.
- Painel separa disponibilidade da API, acurácia condicionada às respostas, decisões pós-política, erros e casos pendentes.
- Corrigida a imagem Docker com cópia obrigatória do arquivo `VERSION`.
- Testes offline para pausa, interrupção, cota 429, retomada, metadados e versão; Docker/Gemini reais não foram executados neste ambiente.

---

## 2.7.0 — Consolidação e avaliação reservada

- Fonte única de versão em `VERSION`; FastAPI e `/api/config` agora compartilham a mesma referência.
- Mensagem do painel de regressão considera o SHA-256 da política efetiva do relatório; elimina comparação fixa incorreta com `2.5.0`.
- Nova bateria de 20 casos sintéticos autorais, congelados antes de qualquer chamada real ao Gemini; modo offline padrão e IA somente por opt-in.
- Testes sem rede reproduzem sequências de erros HTTP 503 e timeouts de transporte, garantindo tentativa limitada e saída sem vazamento de corpo de erro.
- Documentação de apresentação, transparência das limitações e instruções de atualização.

---

## 2.6.0 — Timeout, tentativas visíveis e tratamento de 503 (2026-11-03)

- Gemini SDK configurado explicitamente com **1 tentativa interna** e timeout HTTP por requisição de **20 segundos** (ajustável de 5 a 60 segundos pelo `.env`). Evita multiplicação acidental de tentativas SDK × aplicação.
- No código do ResolveAI: até **3 requisições no total**, esperando 1 segundo e 2 segundos entre erros transitórios. Erros 4xx (incluindo 429) não são repetidos pelo ResolveAI.
- Avaliação `scripts.holdout` imprime **início de cada caso, tentativa atual, erro sanitizado, aviso de repetição e conclusão** imediatamente no terminal. Registros preservam apenas tipo e código HTTP; nunca mostram corpo de erro ou chave.
- O benchmark continua depois de erro final de API, sem executar ações corretivas. `Ctrl+C` interrompe a execução; não use `Ctrl+Z`, que apenas suspende o processo.
- 100 testes automatizados aprovados localmente; incluídos testes de timeout/SDK, logs sanitizados, repetições e continuação após erro.
- **Limite técnico:** timeout do SDK limita a requisição HTTP, não é um cronômetro de interrupção absoluta de todo o processo Python. O Docker Compose e a API Gemini não puderam ser executados neste ambiente; validação com sua própria chave deve ocorrer no Ubuntu.

## 2.5.0 — Telemetria estruturada e confiabilidade da API (2026-11-03)

- 96 testes automatizados aprovados localmente, incluindo regressões de política e de tratamento de falhas da API.
- 3 tentativas no máximo apenas para HTTP 500/502/503/504; espera exponencial de 1 e 2 segundos. Erros 4xx não são repetidos.
- Registros de erro sem conteúdo sensível: tipo e código HTTP quando disponível.
- Melhoria de evidências estruturadas para restart e manutenção; o processo real expõe estado tipado para manutenção e configuração de testes.
- Métricas de desempenho geral e condicionado às respostas válidas, com classificação de erros.
- Conjunto de 28 casos da v2.4 agora usado como regressão, e não como holdout independente.
- Gemini e Docker Compose não foram executados no Ubuntu do usuário a partir deste ambiente.

## 2.3.0 — Validação de evidências e recuperação segura

- Porta independente de evidências antes de **qualquer** mutação, inclusive emulação.
- Análise da ação proposta versus decisão pós-política nos 22 casos sintéticos; erros de API seguem contando como erro.
- Separação de alertas por escolha de ação inadequada, omissão do flag humano e bloqueios da política.
- Reinicialização de serviço só passa quando existem sinais atuais de processo parado e não há erro de configuração contraditório.
- Logs históricos são desconsiderados pela política; sinais estruturados são preferidos. Quando faltam dados, não executa nada.
- Até uma repetição em erros transitórios `ServerError` da API Gemini, sem repetir erros de autenticação.
- 72+ testes automatizados. O sistema permanece uma demonstração isolada, não pronto para produção.

# Histórico de versões

## 2.2.0 — Robustez, evidências conflitantes e defesa contra instruções nos logs

- Nova bateria de 22 casos sintéticos de diagnóstico com logs reescritos, dados conflitantes e mensagens adversárias.
- O gabarito nunca é enviado ao modelo; avaliação somente de leitura sem ações do laboratório.
- Pontuação de correspondência da decisão, escalonamento quando não há evidência, sugestão potencialmente insegura, variações por grupo e erros de API.
- Relatório independente (`challenge_latest.json`) e novo painel **Robustez e segurança**.
- CLI `python -m scripts.challenge --mode offline|ai`; modo IA exige autorização explícita.
- Testes específicos de proteção do gabarito e da necessidade de aprovação, sem envio de chaves ou ações à infraestrutura.

## 2.1.0

- Painel de avaliação independente, com comparativo entre Gemini e baseline determinístico sobre as mesmas evidências.
- Novo cenário de falha indeterminada, que exige encaminhamento em vez de correção inventada.
- Avaliação em lotes de 9 a 27 variações, com hipótese distratora na descrição.
- Métricas de acerto da decisão, recuperação verificada, acerto no encaminhamento, duração e tokens de API quando disponibilizados.
- Chamadas pagas potencialmente possíveis exigem `--mode ai --confirm-api-usage`; ações sensíveis não são aprovadas automaticamente por padrão.
- Cópia de `scripts/` no contêiner para permitir benchmark Docker sem instalar nada no host além do Docker.
- 35 testes automatizados aprovados e 9 casos offline testados de ponta a ponta.
- Docker Compose e benchmark Gemini não foram executados neste ambiente; precisam de validação na máquina do usuário.

## 2.0.0

- Adicionado `real-target`: controlador isolado e processos Python HTTP reais, um por incidente.
- Três incidentes usam falhas reais de processo/configuração no Compose (`web_stopped`, `maintenance_enabled`, `config_missing`).
- Verificação via HTTP para os processos; logs capturados de stdout/stderr; latência de sonda medida.
- Conservados cinco cenários emulados e todo o modo local sem Docker.
- Mantidas allowlists, aprovação humana, Gemini opcional e encaminhamento em falhas.
- Adicionado isolamento de rede Docker e limites de memória/processos.
- Interface agora informa o modo de laboratório e marca cenários disponíveis no modo Docker.
- Testes reais de subprocesso; integração HTTP ponta a ponta validada sem daemon Docker.

### Limitações

- Não testado com daemon Docker neste ambiente. Validar Compose no Ubuntu.
- Sem autenticação para acesso público nem operação em infraestrutura produtiva.
- Reiniciar `real-target` encerra processos de incidentes anteriormente criados.
- Benchmark anterior do baseline não corresponde a desempenho do Gemini.


## 2.4.0 — Casos inéditos e generalização (2026-11-03)
- 28 desafios inéditos, mantidos fora da suíte de robustez de 22 casos.
- Política da v2.3 congelada: hash SHA-256 parcial gravado em relatório para auditoria.
- Nova avaliação read-only com contagem separada de falhas de modelo, erros de API, falhas de política, bloqueios desnecessários e ações inseguras não bloqueadas.
- Nova seção do dashboard: "Casos inéditos", com relatório por grupos e por caso.
- CLI `python -m scripts.holdout` roda offline por padrão, Gemini exige consentimento explícito.
- Os testes não acessam o host nem executam ações no laboratório; a avaliação segue sintética e autoral.
