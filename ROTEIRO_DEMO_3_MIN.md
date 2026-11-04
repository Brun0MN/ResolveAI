# Roteiro de demonstração — aproximadamente 3 minutos

**Objetivo do vídeo:** apresentar problema, solução e resultados de modo verificável, sem prometer automação em infraestrutura de produção.

## 0:00–0:25 — Problema

**Tela:** início do painel ResolveAI.

**Fala sugerida:** "Equipes de TI recebem incidentes que precisam de investigação, correção e confirmação de recuperação. Uma resposta gerada por IA, sozinha, não comprova que o serviço voltou a funcionar. Criei o ResolveAI como um laboratório para testar um fluxo assistido por IA com validação independente."

## 0:25–1:15 — Incidente com correção

**Tela:** caso de serviço web interrompido; histórico de investigação e botão de investigação.

**Fala:** "O sistema coleta saúde, métricas e logs. O Gemini propõe uma ação estruturada; antes de qualquer execução, a política verifica se existem evidências suficientes. Aqui, no processo HTTP de teste, a ação autorizada reinicia o serviço e a verificação confirma HTTP 200."

Se a API estiver instável, utilize uma execução gravada anteriormente ou mostre um registro já salvo **identificando-o como histórico**. Não afirme que houve execução ao vivo se não houve.

## 1:15–1:55 — Exemplo de segurança

**Tela:** incidente sem causa identificável ou painel com encaminhamento.

**Fala:** "Quando os dados não sustentam uma intervenção, o sistema encaminha o caso ao técnico humano. A IA não pode executar comandos arbitrários no computador. Algumas operações de laboratório também exigem aprovação humana explícita."

## 1:55–2:35 — Resultados

**Tela:** painel da avaliação de 20 cenários e resumo dos indicadores.

**Fala:** "Nos 20 casos sintéticos, o Gemini acertou 15 decisões, e a política independente encaminhou as cinco propostas restantes, chegando a 20 decisões consistentes com o gabarito. Isso não equivale a 100% de reparos: alguns resultados corretos são encaminhamentos. Também enfrentei falhas HTTP 503 e implementei repetição controlada, checkpoints e retomada."

## 2:35–3:00 — Limites e próximos passos

**Tela:** diagrama da arquitetura/README no GitHub.

**Fala:** "O resultado é um protótipo de laboratório. Os próximos passos seriam testar incidentes não vistos, avaliar RAG e adicionar identidade e integrações seguras antes de qualquer uso real. O foco foi separar diagnóstico, autorização, execução e medição."

## Checklist de gravação

- [ ] Iniciar serviços no Ubuntu; confirmar `docker compose ps`.
- [ ] Abrir `http://127.0.0.1:8501`; fechar janelas com dados pessoais ou chaves.
- [ ] Preparar um incidente resolvido e um encaminhado.
- [ ] Usar os dados reais da versão 2.8, sem reproduzir cotações inventadas ou métricas estimadas como se fossem medidas.
- [ ] Registrar numa legenda: "Protótipo de laboratório, não conectado a produção".
- [ ] Preferir vídeo de tela legível com áudio claro e poucas transições.
