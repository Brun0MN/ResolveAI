# ResolveAI — Demonstração técnica para a seleção da Softplan

## Mensagem central em 30 segundos

"Desenvolvi uma aplicação web que usa um modelo de linguagem para identificar a causa provável de incidentes fictícios de infraestrutura. O agente consulta sinais estruturados e logs de um laboratório Docker, propõe apenas ações permitidas e uma segunda política independente decide se essas ações podem ser executadas. O sistema verifica o retorno do serviço e registra o processo para auditoria. Também desenvolvi testes de diagnóstico, incluindo cenários com informações insuficientes e tentativas de manipular o agente." 

**Atenção:** descreva seu próprio papel com precisão e deixe claro onde ferramentas de IA auxiliaram a implementação. Não diga que o sistema resolve problemas de produção; ele demonstra laboratório com processos descartáveis e cenários emulados.

## Demonstração de 3 a 5 minutos

1. Mostrar painel, modelo ativo (Gemini ou regras offline) e restrição ao ambiente Docker.
2. Criar o incidente "Serviço web interrompido"; executar diagnóstico e mostrar o resultado HTTP 200 e o registro de auditoria. Indicar que os serviços são descartáveis.
3. Criar "Variável de configuração ausente"; demonstrar que a ação é **outra** (`restore_demo_config`).
4. Mostrar um caso incerto que é encaminhado, não executado.
5. Mostrar a seção **Regressão** e a seção **Bateria congelada**, distinguindo taxa do modelo, taxa após política e falhas da API.
6. Encerrar com trade-offs: falsos positivos, falsos bloqueios, sobrecarga da API, falta de auditoria externa e necessidade de autenticação antes de uso público.

## Arquitetura resumida

Navegador → FastAPI + SQLite → coletor do laboratório → modelo Gemini (nuvem, opcional) → política determinística → ações fixas autorizadas → nova consulta de saúde.

## O que dizer sobre os números

Use **somente resultados exibidos** na sua instalação; registre versão do projeto, hash da política e quantidade de casos. A bateria de 28 casos foi usada em ajustes e **não é mais independente**. A bateria nova de 20 casos também é sintética e escrita pelos autores deste projeto, apesar de ter sido congelada.

## Antes da apresentação

- Verifique se o modelo está ativado no painel, sem mostrar sua chave.
- Rode `docker compose ps` para confirmar todos os contêineres saudáveis.
- Prepare captura de tela e vídeo local, caso o Google esteja indisponível.
- Nunca exponha a porta do projeto à internet sem autenticação e avaliações adicionais.
- Confira se o repositório no GitHub **não inclui** `.env`, chaves, dados SQLite ou logs privados.
