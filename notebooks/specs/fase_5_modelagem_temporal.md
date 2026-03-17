# Fase 5: Modelagem Temporal (Simplificada)

## Decisão de escopo

Deep learning (LSTM/GRU/CNN) **descartado** — dataset pequeno (~70 positivos por bacia) não justifica. Foco apenas em features temporais clássicas (lags + rolling stats) alimentando os modelos da Fase 4.

## Objetivo

Testar se features de lag e rolling stats melhoram o baseline clássico. Responde: **"Adicionar contexto temporal explícito às features melhora a predição?"**

## Inputs

| Arquivo | Descrição | Origem |
|---------|-----------|--------|
| `dados/cemaden_diario_bacia.parquet` | Chuva diária por bacia (resolução horária) | Fase 2 |
| `dados/features_24h.parquet` | Features base | Fase 3 |
| `dados/target_por_bacia.parquet` | Target binário | Fase 3 |
| `modelos/metricas_baseline.json` | Benchmark da Fase 4 | Fase 4 |

## Outputs

| Artefato | Descrição |
|----------|-----------|
| `dados/features_temporal.parquet` | Features 24h + lags + rolling stats |
| `modelos/temporal_<bacia>.pkl` | Melhor modelo re-treinado (se bater baseline) |
| `modelos/metricas_temporal.json` | Métricas comparativas |

## Células planejadas

1. **Hipótese** — enchentes têm precursores temporais (ex: 3h de chuva crescente) que features agregadas perdem
2. **Feature engineering temporal** — lags (t-1..t-6 dias) das features principais, rolling mean/max/std sobre janelas de 3/5/7 dias, trend (diferença entre janelas)
3. **Análise de correlação** — novas features vs target
4. **Re-treinar campeão da Fase 4** com features expandidas
5. **Comparação side-by-side com baseline** — as features temporais ajudaram?
6. **Export** se bater baseline, documentar se não bater

## Decisões tomadas

- Deep learning descartado — dataset pequeno (~70 positivos por bacia) não justifica

## Decisões pendentes

_(nenhuma ainda)_

## Dependências

Fases 3 e 4 completas.
