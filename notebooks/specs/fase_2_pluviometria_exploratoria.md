# Fase 2: Exploratória de Pluviometria + Correlação de Estações

## Objetivo

Entender padrões espaciais e temporais da chuva em Santo André. Responde: **"Como as estações se correlacionam? O que define precipitação extrema? Quais estações são representativas de cada bacia?"**

## Inputs

| Arquivo | Descrição | Origem |
|---------|-----------|--------|
| `dados/cemaden_bruto.csv` | 26M registros horários | Raw |
| `dados/estacoes_bacia.json` | Mapeamento estação → bacia | Fase 1 |
| `dados/chamados_enchente.parquet` | Chamados validados | Fase 1 |
| `dados/piscinoes_abc.json` | 27 piscinões com capacidade e ano de inauguração | Raw |

## Outputs

| Artefato | Descrição |
|----------|-----------|
| `dados/cemaden_limpo.parquet` | Filtrado Santo André, com metadados de estação |
| `dados/cemaden_diario_bacia.parquet` | Chuva diária agregada por bacia (max, sum, mean) |
| `dados/percentis_chuva.json` | Thresholds de percentil por bacia (p50, p75, p90, p95, p99) |

## Células planejadas

1. **Carga + filtro Santo André** — ~1.9M linhas de 26M
2. **Inventário de estações** — código, nome, lat/lon, período ativo, cobertura (% de horas com leitura)
3. **Heatmap de cobertura temporal** — estações × meses
4. **Distribuição de chuva por estação** — histograma (log), percentis, máximos
5. **Análise sazonal** — box plots por mês, confirmar estação chuvosa (Nov-Abr)
6. **Matriz de correlação entre estações** — Pearson/Spearman diário
7. **Agregação por bacia** — usando `estacoes_bacia.json` (max entre estações da bacia)
8. **Percentis de chuva por bacia** → salvar `percentis_chuva.json`
9. **Cruzamento com datas de enchente** — perfil de chuva por estação em cada evento confirmado
10. **Contexto piscinões** — timeline de inaugurações × frequência de enchentes por ano
11. **Preview de features de janela** — (6h/12h/24h/48h) para amostras de eventos

## Decisões tomadas

_(nenhuma ainda)_

## Decisões pendentes

- Agregação por bacia: max vs mean vs sum?
- Excluir estação Paranapiacaba (montanha, longe de enchentes urbanas)?
- Estações série G: mesma estação com código atualizado ou estação distinta?
- Mínimo de estações reportando para considerar dia válido?

## Dependências

Fase 1 completa (precisa de `estacoes_bacia.json` e `chamados_enchente.parquet`).
