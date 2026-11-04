## Atualização v2.8: disponibilidade e honestidade da medição

Em um teste reservado realizado pelo usuário em Ubuntu em 04/11/2026, apenas quatro dos 20 casos receberam respostas do provedor; 16 tiveram erros 503/504 ou timeout. O objetivo da v2.8 é **não insistir em chamadas quando o serviço estiver instável**, salvar checkpoints e retomar as faltantes. A taxa de acerto calculada sobre apenas quatro respostas é uma estimativa extremamente limitada e não demonstra confiabilidade geral.

Destaques técnicos para explicar à banca: separação de disponibilidade de precisão; circuit breaker; retomada compatível com hash da política e dos casos; auditoria de falhas sem expor credenciais; execução de testes de segurança com erros simulados e sem consumo de API. Nenhum desses recursos torna o protótipo pronto para produção.

# ResolveAI — roteiro de apresentação à banca

## Proposta

Incidentes de TI exigem investigação, análise de evidências, aplicação de uma correção autorizada e confirmação de que o serviço recuperou. O ResolveAI é um protótipo que demonstra esse ciclo em um **laboratório isolado que combina processos reais de teste com cenários emulados**.

## Problema e hipótese

**Problema:** uma solução que somente recomenda um comando não comprova resolução e pode incentivar ações perigosas.

**Hipótese:** uma arquitetura com ferramentas restritas, verificação posterior e aprovação humana para operações sensíveis pode automatizar o ciclo básico de investigação e tratamento em laboratório de forma mais auditável.

## Implementação

- FastAPI para rotas HTTP e backend.
- SQLite para incidentes e eventos auditáveis.
- Investigação de saúde, logs, métricas e configuração via ferramentas HTTP restritas.
- Gemini API (opcional) para escolher e justificar uma operação em formato JSON tipado.
- Política independente do modelo que rejeita operações fora da allowlist ou com confiança abaixo do limiar.
- Aplicação da ação somente no cenário isolado, seguida por teste de saúde verificável.
- Na versão 2.1, três cenários operam subprocessos HTTP reais dentro do Docker: serviço interrompido, modo manutenção e configuração inválida. Seis outros são emulados, um deles com causa desconhecida.
- Três operações exigem aprovação humana antes da execução.
- Modo baseline offline determinístico para reproduzir testes sem custo.

## Avaliação comprovada até o momento

**Código:** 35 testes automatizados aprovados. Em uma avaliação ponta a ponta com 9 cenários, **apenas em modo regras offline**, o sistema acertou 9/9 decisões e 5/8 incidentes acionáveis foram verificados como recuperados automaticamente; três ações continuaram pendentes de aprovação, como prevê a política. O cenário sem evidência suficiente foi encaminhado corretamente. Isso **não é desempenho do Gemini** e não deve ser apresentado como prova de generalização.

**Testes manuais anteriores com Gemini:** o usuário demonstrou dois casos resolvidos (reinicialização de serviço e restauração de configuração), ambos em processos isolados com verificação HTTP 200. São evidências pontuais, não uma avaliação sistemática.

**Pendente:** executar o benchmark com Gemini no Ubuntu e coletar os resultados, especialmente as divergências; o Docker Compose não foi executado aqui. A baseline contém assinaturas explícitas do laboratório, portanto sua precisão alta é esperada e representa principalmente um teste de integração. Custo em moeda não é medido; contagens de tokens podem aparecer no relatório quando o provedor fornecer metadados.

## Perguntas para estar pronto a responder

**Por que não quatro LLMs diferentes?** A arquitetura usa estágios especializados, mas apenas um modelo para diagnóstico. Permite resultados mais rápidos, menor custo e menos superfícies de falha. Multiagentes autônomos poderiam ser avaliados futuramente.

**A IA executa comandos Linux?** Não. Ela seleciona operações fixas; o controlador do laboratório consegue iniciar e encerrar exclusivamente subprocessos HTTP predeterminados dentro do contêiner. A IA não executa shell, SSH ou comandos no host.

**Como vocês evitam que a IA marque falsos sucessos?** Uma verificação independente consulta o estado da aplicação após o reparo. Se não houver saúde verificada, escala-se para um humano.

**O sistema já foi validado em produção?** Não. É um protótipo de laboratório. Para uso real, precisaria de autenticação, limites de acesso, observabilidade, segurança operacional, implantação apropriada e autorização formal.

**A IA escreveu o código?** Ferramentas de IA podem auxiliar na implementação, mas a contribuição técnica a demonstrar está nas escolhas de arquitetura, testes, avaliação crítica, correções e entendimento do funcionamento. Não atribua experiências ou experimentos que você não realizou.

## Proposta de fala (aprox. 90 segundos)

> Desenvolvi uma demonstração de resolução assistida por inteligência artificial de incidentes de TI. Diferentemente de um chatbot de suporte, o protótipo coleta evidências de um laboratório, toma uma decisão baseada em informações observáveis, aplica apenas ações de uma lista segura e verifica se o serviço se recuperou. Decisões mais sensíveis exigem aprovação humana. Separei a decisão da IA da política de segurança e mantive uma trilha de auditoria completa. Preparei cenários de laboratório, testes automatizados e um benchmark reproduzível. A versão 2.1 usa três tipos de falha real em processos HTTP isolados e seis cenários emulados, incluindo um que deve ser encaminhado. Acrescentei um benchmark em lotes para medir acertos, falhas, escalonamentos e recuperações, sem confundir regras offline com Gemini.

Adapte a fala somente após você mesmo explorar e compreender a implementação.

## Evidência adicional — ResolveAI 2.3 (a completar no seu computador)

Esta versão adiciona um conjunto **somente diagnóstico** com 22 exemplos fictícios de logs inesperados, conflitantes e adversários. A primeira execução local por regras correspondeu a 4/22 decisões (18,2%), pois as assinaturas de texto foram reformuladas deliberadamente. Este é apenas um *baseline limitado*, **não é um teste da IA** e não é apropriado para declarar que a IA é melhor sem medir suas decisões no mesmo conjunto.

Após executar a opção `--mode ai` no Ubuntu, registre os resultados reais: número de casos, modelo e data; acurácia de decisão e do baseline; acerto de encaminhamento; taxa nos casos de injeção; e erros de API. Não apresente os números dos relatórios `offline` como se fossem do Gemini. A análise deve mencionar que o gabarito é sintético e foi criado manualmente.

### v2.4 — Generalização em dados sintéticos inéditos
Foi criado um conjunto de 28 casos que não fazem parte das baterias usadas para desenvolver a política v2.3. A política ficou intocada para permitir identificar falhas novas: propostas sem evidência, aprovações indevidas e falsos bloqueios. Os resultados separados do modelo e da política permitem uma apresentação honesta, sem alegar validade externa nem sucesso em produção. O teste usa apenas dados fictícios e não realiza operações de correção.
