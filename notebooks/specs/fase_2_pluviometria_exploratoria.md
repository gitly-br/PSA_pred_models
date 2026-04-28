# Fase 2: Validação Regional de Estações CEMADEN

## Objetivo

Determinar quais estações CEMADEN são relevantes para cada bacia hidrográfica, usando os eventos de enchente confirmados como âncora. Responde: **"Quais estações precisam ser consideradas para cada bacia?"**

## Inputs

| Arquivo | Descrição | Origem |
|---------|-----------|--------|
| `dados/cemaden_bruto.csv` | 26M registros horários | Raw |
| `dados/chamados_por_bacia.parquet` | Chamados validados com timestamp bruto (pré-`dt_ajustado`) e bacia | Fase 1 |

## Outputs

| Artefato | Descrição |
|----------|-----------|
| `dados/estacoes_bacia.json` | Mapeamento estação → bacia(s) validado por votação |

## Células planejadas

1. **Inventário de estações** — código, série (A/G), lat/lon, período ativo, % cobertura
2. **Carga de chamados** — puxa `chamados_por_bacia.parquet` do notebook 1 (timestamp bruto + bacia)
3. **Esquema de votação** — para cada evento × estação, calcula 3 métricas:
   - **Frequência** (necessidade): quantas vezes a estação registrou ≥ limiar na janela antes do chamado / total de eventos na bacia
   - **Especificidade**: votos para essa bacia / votos totais da estação (discrimina estações que "disparam pra tudo")
   - **Intensidade média**: média de precipitação na janela nos eventos da bacia (independente de limiar fixo)
4. **Mapas de relevância** — 1 mapa de Santo André por bacia; estações plotadas com cor/tamanho pelo score de relevância (plotly mapbox)
5. **Decisão e export** — dropdown para confirmar/ajustar atribuição → salva `estacoes_bacia.json`

## Decisões tomadas

_(nenhuma ainda)_

## Decisões pendentes

- Série A/G: períodos sequenciais (concatenar) ou sobrepostos (estações distintas)? Verificar nos dados antes de implementar célula 3.
- Score combinado (único colorscale no mapa) ou 3 dimensões visuais separadas (cor, tamanho, opacidade)?
- Excluir estação Paranapiacaba (montanha, longe de enchentes urbanas)?
- Janela temporal de votação (candidatos: 3h, 6h, 12h) — sensibilidade a testar na célula 3.
- Limiar de precipitação para voto binário.

## Dependências

Fase 1 precisa exportar `dados/chamados_por_bacia.parquet` com colunas: `data_hora_chamado`, `bacia`, `id_chamado` (timestamp bruto, antes do `dt_ajustado`).
