# ResolveAI — resumo para inscrição e portfólio

## Descrição curta (copiar/adaptar)

Protótipo de plataforma para diagnóstico e tratamento assistido por inteligência artificial de incidentes de TI. A solução coleta evidências de um laboratório isolado, utiliza o Gemini para propor diagnósticos e aplica uma política independente que limita as ações autorizadas. As correções permitidas são verificadas por testes de saúde e todas as etapas são registradas para auditoria.

## Problema e diferencial

O problema é que sugerir uma solução não garante que ela seja correta, segura ou que realmente recupere o serviço. O ResolveAI demonstra um fluxo completo: **observar → diagnosticar → validar → executar no laboratório → verificar**. Operações sensíveis exigem aprovação humana e ausência de evidência leva ao encaminhamento.

## Tecnologias

Python, FastAPI, Gemini API, Docker Compose, SQLite, HTML/CSS/JavaScript, pytest.

## Resultados que podem ser citados

- 20 casos sintéticos concluídos na avaliação do operador: 75% de acerto da decisão bruta do Gemini e 100% de concordância com o gabarito após aplicar a política de segurança.
- 120 testes automatizados Python aprovados na preparação desta versão de portfólio.
- Recuperações demonstradas em serviços HTTP de laboratório, com verificação posterior.

**Contextualização obrigatória:** os 20 casos são sintéticos, a política pode encaminhar corretamente sem reparar, e as métricas não equivalem a resultados de produção.

## Papel da inteligência artificial

A IA é utilizada **durante a execução**, na interpretação das evidências e recomendação de uma ação. Ferramentas de IA também auxiliaram no desenvolvimento do código. A política de segurança, as ferramentas de laboratório e a decisão de autorizar reparos são programadas separadamente do modelo.

## O que o sistema não é

Não é uma solução pronta para monitoramento de infraestrutura real; não inclui RAG nem quatro agentes LLM independentes. Esses recursos são opções futuras, não capacidades já entregues.

## Texto de apresentação sugerido

"Escolhi um problema real de suporte e operações de TI: a distância entre diagnosticar uma falha e resolvê-la com segurança. Desenvolvi, com assistência de IA, um protótipo que recebe incidentes de laboratório, analisa evidências com Gemini, passa propostas por uma política independente e verifica se ações autorizadas recuperam o serviço. Também criei avaliações para detectar falhas de diagnóstico e aprimorei a robustez da integração após encontrar indisponibilidade da API. O resultado demonstra não apenas integração de um modelo, mas também validação, observabilidade e análise crítica das limitações."

**Nota de transparência:** ajuste "desenvolvi" para refletir fielmente sua contribuição e não atribua a si autoria manual de componentes produzidos por ferramentas de IA.
