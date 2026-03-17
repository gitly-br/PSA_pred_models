# CLAUDE.md

## Project Overview

PSA (Prefeitura de Santo André) — sistema de predição de enchentes por bacia hidrográfica. Pipeline de notebooks marimo (`.py`) para exploração, feature engineering e modelagem.

## Modo de Trabalho

**PAIR PROGRAMMING: discutir cada célula antes de implementar.** Não avançar para a próxima célula sem alinhamento. Mostrar o que cada célula faz, o que revela nos dados, e perguntar se faz sentido antes de continuar. O usuário quer participar de cada decisão.

Specs em `specs/` são guias de intenção, não receitas. Cada célula ainda deve ser discutida antes de implementar, mesmo que o spec já descreva o que fazer.

## Protocolo de sessão

**Início:** ler `specs/progresso.md` e o spec da fase ativa. Resumir onde paramos e qual o próximo passo.

**Final:** atualizar `specs/progresso.md` com o que foi feito, decisões tomadas, e próximo passo. Quando uma decisão pendente for resolvida, atualizar também o spec da fase (mover de "Pendentes" para "Tomadas").

## Environment

```bash
uv sync                          # instalar deps
uv run marimo edit <notebook>.py # rodar notebook interativo
uv run marimo check <notebook>.py # verificar notebook
```

## Stack

- **marimo** — notebooks reativos (`.py`, não `.ipynb`)
- **polars** — dataframe principal (não pandas)
- **plotly** — visualização
- **scikit-learn** — modelos ML

## Pipeline de Fases

1. `chamados_exploratoria.py` — exploratória + validação de labels de enchente
2. `pluviometria_exploratoria.py` — exploratória pluviometria + correlação estações
3. `processamento_features.py` — feature engineering (datasets 24h/48h)
4. `modelagem_classica.py` — ML clássico (baseline)
5. `modelagem_temporal.py` — features temporais (lags + rolling stats)
6. `forecast_integracao.py` — integração com dados de forecast

## Storytelling nos notebooks

- Sem exibições brutas de DataFrame — usar `mo.stat`, callouts ou gráficos
- UI interativa só enquanto a decisão não foi tomada; depois vira constante
- Cada seção responde uma pergunta clara, anunciada num `mo.md` de cabeçalho

## Referências

| O quê | Onde |
|-------|------|
| Progresso atual e onde retomar | [`specs/progresso.md`](specs/progresso.md) |
| Spec de cada fase | `specs/fase_N_<nome>.md` |
| Artefatos e dependências entre fases | [`specs/artefatos_pipeline.md`](specs/artefatos_pipeline.md) |
| Decisões técnicas e lições dos notebooks antigos | [`specs/decisoes_tecnicas.md`](specs/decisoes_tecnicas.md) |
| Dados de entrada (schemas, colunas) | [`specs/decisoes_tecnicas.md` § Data Schema](specs/decisoes_tecnicas.md) |
