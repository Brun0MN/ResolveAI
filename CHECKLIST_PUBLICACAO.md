# Checklist de publicação no GitHub

## Antes da publicação

- [ ] Ler o README, entender arquitetura e explicar o papel real do Gemini.
- [ ] Confirmar que `VERSION` é `2.8.0` e que o `Dockerfile` contém `COPY VERSION ./VERSION`.
- [ ] Revisar `.env` e manter a chave Gemini fora do repositório.
- [ ] Revisar se não há relatórios privados em `data/`, resultados brutos, capturas de tela ou logs.
- [ ] Rodar `python -m pytest -q`; opcionalmente testar `./scripts/start_docker.sh` no Ubuntu.
- [ ] Verificar se os exemplos e limitações do README continuam verdadeiros.
- [ ] Adicionar imagens ou vídeo **apenas depois** de remover dados sensíveis.

## Publicar (somente se você decidir)

No terminal, dentro da pasta `resolveai`:

```bash
git init
git add .
git status
# Revise a lista com cuidado; nunca deve aparecer .env
git commit -m "ResolveAI 2.8: protótipo de diagnóstico assistido por IA"
```

Crie um repositório vazio no GitHub pela interface web e siga os comandos fornecidos pelo próprio GitHub para associar `origin` e fazer o primeiro push. **Este pacote não publica automaticamente.**

## Depois de publicar

- [ ] Abrir o link do repositório sem fazer login e confirmar que o README aparece corretamente.
- [ ] Confirmar que nenhum segredo ou dado privado foi incluído.
- [ ] Inserir link do vídeo de demonstração quando estiver pronto.
- [ ] Na inscrição, explicar exatamente quais partes foram geradas com assistência de IA e quais foram testadas por você.
