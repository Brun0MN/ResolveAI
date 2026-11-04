# ResolveAI 2.7 — Bateria congelada de diagnóstico

## O que ela é

20 casos novos e **sintéticos, elaborados pelo autor deste projeto**. Nunca foram consultados durante o ajuste da política v2.7. As ações esperadas, os motivos e os identificadores **não são enviados ao Gemini**. O conjunto foi congelado antes de qualquer teste com o modelo em v2.7; o hash SHA-256 integral é:

`09ca2a46eb56b5d0d2aa2aca22a62deaef5f7beac9988a5e5fc3bf4b0e31edd5`

A política atual pode ser identificada também pelo SHA-256 parcial exibido no painel. Não ajuste a política após ver as respostas desse conjunto e continue chamando os resultados de "avaliação do conjunto reservado"; se houver ajustes futuros baseados nesses casos, mude sua classificação para **regressão** e crie outra bateria separada.

## O que ela não é

Não é uma validação **independente por terceiros**, nem representa tickets reais, nem mede segurança operacional fora do laboratório. A taxa de acerto depois da política não representa necessariamente a taxa de acerto do modelo. Não se deve declarar confiabilidade generalizada, nem comparar diretamente custos sem conhecer a contagem de chamadas e preços correntes.

## Executar com custo zero de API

```bash
docker compose exec -T app python -m scripts.reserved --mode offline --limit 20
```

Isso executa regras locais, não Gemini. Não executa ações corretivas. No painel, a aba **Bateria congelada** exibirá o resultado como "Regras offline".

## Executar com Gemini (opcional)

```bash
docker compose exec -T app python -m scripts.reserved --mode ai --confirm-api-usage --limit 20
```

Chamadas consomem quota e **podem gerar cobrança em projetos que tenham faturamento ativado**. Se preferir, teste primeiro `--limit 3`. Se a chamada falhar, o caso será marcado como erro, sem crédito de acerto. Os casos são apenas de diagnóstico, sem aplicação das ações.

## Indicadores necessários

- Acurácia bruta do modelo em todos os casos, incluindo falhas de API como erros.
- Acurácia do modelo entre as respostas válidas.
- Acurácia pós-política, medida separadamente da bruta.
- Falsos bloqueios, recomendações arriscadas e erros HTTP.
- Distribuição de grupos e consumo de tokens reportado, quando a API fornecer os valores.

**Não rode benchmarks com sua chave durante uma sessão de entrevista sem confirmar antes o limite disponível.**
