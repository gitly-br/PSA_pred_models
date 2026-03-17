# Fase 3: Feature Engineering

## Objetivo

Construir a matriz de features para modelagem. Responde: **"Qual é o dataset final, por bacia, com target binário enchente/não-enchente e features derivadas de chuva?"**

## Inputs

| Arquivo | Descrição | Origem |
|---------|-----------|--------|
| `dados/cemaden_diario_bacia.parquet` | Chuva diária agregada por bacia | Fase 2 |
| `dados/chamados_enchente.parquet` | Chamados validados | Fase 1 |
| `dados/percentis_chuva.json` | Thresholds de percentil por bacia | Fase 2 |
| `dados/alagamentos_bacias.csv` | Datas com flags por bacia | Raw |

## Outputs

| Artefato | Descrição |
|----------|-----------|
| `dados/features_24h.parquet` | Uma linha por (data, bacia), features de janela 24h |
| `dados/features_48h.parquet` | Idem com janela 48h |
| `dados/target_por_bacia.parquet` | Target binário por (data, bacia) |

## Células planejadas

1. **Carga dos inputs**
2. **Construção do target** — `enchente = True` se pelo menos 1 chamado `confirmado_chuva_bacia` naquela bacia+data. Cross-reference com `alagamentos_bacias.csv`
3. **Análise de desbalanceamento** — (~10:1). Impacto do filtro sazonal (remover Mai-Out)
4. **Features de janelas de chuva** — `chuva_acum_Nh` (6/12/24/48/72h), `chuva_max_1h`, `chuva_max_3h`, `horas_com_chuva`, `horas_intensas_10mm`, `chuva_delta_6h`
5. **Features de agregados temporais** — média por bloco de 6h (0-6, 6-12, 12-18, 18-24), delta entre blocos consecutivos
6. **Features de antecedente** — `dias_desde_ultima_chuva` (>5mm), `chuva_acum_7d` (proxy saturação solo)
7. **Features cross-bacia** — chuva acumulada nas bacias vizinhas (upstream)
8. **Features de sazonalidade** — mês, dia do ano, flag estação chuvosa, encoding seno/cosseno
9. **Indicadores de extremo** — flags `acima_p75`, `acima_p90`, `acima_p95` usando percentis da Fase 2
10. **Filtro sazonal** — remover Mai-Out, mostrar impacto no balance
11. **Split temporal** — train 2016-2022, test 2023-2024
12. **Análise de correlação entre features, VIF**
13. **Export dos parquets**

## Decisões tomadas

- Open Weather (temperatura, umidade, visibilidade) **NÃO** entra aqui — só na Fase 6. Fases 3-4 são CEMADEN-only.

## Decisões pendentes

- 24h vs 48h: qual o primário? Construir ambos e comparar na Fase 4
- Quais bacias são upstream/downstream? Precisa contexto hidrológico
- Target: usar só `confirmado_chuva_bacia` ou também `alagamentos_bacias.csv`?

## Dependências

Fases 1 e 2 completas.
