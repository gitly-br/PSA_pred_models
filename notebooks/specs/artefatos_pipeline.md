# Artefatos do Pipeline

Tabela de dependência entre artefatos produzidos e consumidos por cada fase.

## Dados intermediários

| Artefato | Produzido | Consumido |
|----------|-----------|-----------|
| `dados/chamados_enchente.parquet` | Fase 1 | Fases 2, 3 |
| `dados/estacoes_bacia.json` | Fase 1 | Fases 2, 3 |
| `dados/datas_enchente_consolidadas.csv` | Fase 1 | Fase 3 |
| `dados/cemaden_limpo.parquet` | Fase 2 | Fase 3 |
| `dados/cemaden_diario_bacia.parquet` | Fase 2 | Fases 3, 5, 6 |
| `dados/percentis_chuva.json` | Fase 2 | Fases 3, 4 |
| `dados/features_24h.parquet` | Fase 3 | Fases 4, 5, 6 |
| `dados/features_48h.parquet` | Fase 3 | Fase 4 |
| `dados/target_por_bacia.parquet` | Fase 3 | Fases 4, 5 |

## Modelos

| Artefato | Produzido | Consumido |
|----------|-----------|-----------|
| `modelos/baseline_<bacia>.pkl` | Fase 4 | Fase 6 |
| `modelos/metricas_baseline.json` | Fase 4 | Fases 5, 6 |
| `modelos/temporal_<bacia>.pkl` | Fase 5 | — |
| `modelos/forecast_<bacia>.pkl` | Fase 6 | — |
| `dados/pipeline_config.json` | Fase 6 | Produção |
