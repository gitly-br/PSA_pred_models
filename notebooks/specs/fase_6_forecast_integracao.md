# Fase 6: Integração com Forecast

## Objetivo

Integrar dados de forecast para predição operacional. Responde: **"Conseguimos predizer enchentes usando dados de previsão disponíveis ANTES do evento?"**

## Inputs

| Arquivo | Descrição | Origem |
|---------|-----------|--------|
| `dados/features_24h.parquet` | Features base | Fase 3 |
| `modelos/baseline_<bacia>.pkl` | Modelos treinados | Fase 4 |
| `dados/cemaden_diario_bacia.parquet` | Chuva histórica | Fase 2 |
| API de forecast | Open Weather ou Open-Meteo | Externo |

## Outputs

| Artefato | Descrição |
|----------|-----------|
| `dados/forecast_historico.parquet` | Dados de forecast históricos alinhados com período de treino |
| `modelos/forecast_<bacia>.pkl` | Modelos treinados em features de forecast |
| `modelos/metricas_forecast.json` | Comparação: histórico-only vs forecast-only vs combinado |
| `dados/pipeline_config.json` | Config operacional |

## Células planejadas

1. **O problema operacional** — dados históricos só existem DEPOIS do evento. Produção precisa de forecast
2. **Avaliação de APIs** — Open Weather (usado no V1, tier pago para histórico) vs Open-Meteo (grátis, tem arquivo de forecast histórico)
3. **Download de forecasts históricos** para período de treino
4. **Feature engineering de forecast** — umidade média/delta por bloco 6h, vento, probabilidade de precipitação, temperatura/ponto de orvalho
5. **Três variantes de modelo por bacia** — histórico-only, forecast-only, combinado
6. **Simulação operacional** — no tempo T, usar chuva até T + forecast T→T+24h
7. **Comparação com Fase 4**
8. **Design do pipeline operacional** — input → features → modelo → probabilidade → nível de alerta
9. **Export config operacional**

## Lições dos notebooks antigos

- **Melhores features (forecast):** delta umidade 0-6h, delta ângulo do vento, umidade média 6-12h, probabilidade de precipitação, delta convecção
- **Forecast obrigatório em produção** — dados históricos não existem em tempo real; modelo operacional precisa de forecast

## Decisões tomadas

_(nenhuma ainda)_

## Decisões pendentes

- Qual API de forecast? Candidatos: Open-Meteo (grátis, sem key, tem histórico) vs Open Weather (usado no V1, tier pago). Decidir quando chegar nesta fase
- Viável recuperar forecast histórico para todo o período de treino?
- Modelo operacional roda horário ou diário?
- Threshold de alerta: que taxa de falso positivo é aceitável para Defesa Civil?
- V1 usou visibilidade e ponto de orvalho como top features — nem todas APIs têm isso

## Dependências

Fases 3 e 4 completas, configuração de API key.
