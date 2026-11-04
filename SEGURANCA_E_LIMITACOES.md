# Segurança e limitações

## Salvaguardas presentes

- O modelo recebe evidências selecionadas, não uma sessão de terminal.
- Ferramentas de consulta predefinidas; ações corretivas limitadas a uma lista explícita.
- Política independente valida evidências e exige aprovação humana em operações mais sensíveis.
- Se a API falhar ou a ação não for sustentada, o fluxo encaminha o incidente sem executar correções adicionais.
- Revalidação do estado depois da correção e registro de auditoria em SQLite.
- Docker Compose limita recursos do laboratório e expõe a interface em `127.0.0.1:8501` na configuração fornecida.

## O que **não** foi resolvido

- **Não há autenticação/RBAC de produção.** Não publicar na internet como está.
- Não há gestão corporativa de segredos, trilhas imutáveis, aprovação associada a identidade autenticada ou isolamento formalmente auditado.
- O laboratório contém processos reais de teste, porém não diagnostica a infraestrutura de empresas nem possui integrações SSH em servidores reais.
- Logs e trechos recuperados de sistemas externos seriam dados não confiáveis: jamais tratá-los como instruções para alterar a política.
- As avaliações são sintéticas e a política pode bloquear ações válidas ou falhar em condições não cobertas.
- O uso do Gemini depende da disponibilidade do provedor, de limites da API e das condições do projeto configurado no Google AI Studio.

## Antes de compartilhar no GitHub

1. Não comitar `.env`, chaves, tokens ou capturas que exibam credenciais.
2. Conferir `git status` e `git diff --cached` antes de cada publicação.
3. Não publicar relatórios brutos de organizações, logs pessoais ou dados de terceiros.
4. Indicar claramente o caráter experimental e descrever assistência de IA no desenvolvimento.
5. Revisar a licença MIT e o conteúdo publicado antes de tornar o repositório público.

## Evolução segura para uso real

Antes de conectar qualquer sistema de produção, exigir ambientes de homologação, revisão de ameaças, identidade verificável, políticas por papel, aprovações rastreáveis, ferramentas somente leitura inicialmente, escopos de rede restritos, mecanismos de rollback e validação externa.
