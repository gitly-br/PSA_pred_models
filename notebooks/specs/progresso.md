# Progresso do Pipeline

## Fase ativa: 1 — chamados_exploratoria.py

**Status:** Notebook implementado e refatorado. Cobre: imports/helpers, carga chamados, normalização bairros, join bacias, filtro 809.x, carga CEMADEN, filtro outliers CEMADEN, agregação horária, validação multi-janela com sliders, gráfico de perfil de chuva interativo, ajuste de horário (`dt_ajustado`), janelas de evento (`event_start`/`event_end`), dias suspeitos sem confirmação, e análise de confirmados sem chamados.

**Próximo passo:** Consolidar datas externas (4 arquivos de validação) — ver spec Fase 1 § "Células novas".

**O que falta no notebook:**
- Consolidar datas externas e cruzar com chamados
- Mapa de estações CEMADEN + centróides por bacia
- Mapeamento estação → bacia → export `estacoes_bacia.json`
- Validação refinada por bacia (`confirmado_chuva_bacia`)
- Summary stats com `mo.stat`
- Export `chamados_enchente.parquet` e `datas_enchente_consolidadas.csv`

## Artefatos

| Artefato | Existe? |
|----------|---------|
| `dados/chamados_enchente.parquet` | Não |
| `dados/estacoes_bacia.json` | Não |
| `dados/datas_enchente_consolidadas.csv` | Não |
| `dados/cemaden_limpo.parquet` | Não |
| `dados/cemaden_diario_bacia.parquet` | Não |
| `dados/percentis_chuva.json` | Não |
| `dados/features_24h.parquet` | Não |
| `dados/target_por_bacia.parquet` | Não |

## Fases seguintes

| Fase | Status |
|------|--------|
| 2. pluviometria_exploratoria | Não iniciada |
| 3. processamento_features | Não iniciada |
| 4. modelagem_classica | Não iniciada |
| 5. modelagem_temporal | Não iniciada |
| 6. forecast_integracao | Não iniciada |

## Notas da última sessão (2026-03-16)

- Refatoração completa de performance e qualidade: Polars nativo em todo o notebook, Altair 6.0 sem `.to_pandas()`, células de constantes e `lims` separadas
- Filtro de outliers CEMADEN com `mo.ui.number` e stats de remoção
- Gráfico de perfil interativo: seleção por clique, janela 72h relativa ao chamado mais cedo, banda/risco cinza para chamados, banda/risco laranja para evento de chuva
- Lógica de `dt_ajustado`: pico de 1h dentro da melhor janela acumulada (1h/3h/6h) nas 72h anteriores
- Janelas de evento (`event_start`/`event_end`): expande do pico enquanto chuva ≥ limiar configurável, máx 6h por lado; `only_1h` → ponto único
- Tabela de dias suspeitos (>10 chamados 809.x sem confirmação); pesquisa confirmou 2019-03-10 como evento extremo (72-90mm/h, decreto de calamidade) — já estava em `alagamentos_confirmados.csv`
- Nova seção "Alagamentos confirmados sem chamados": anti-join ±3 dias, dropdown de seleção, gráfico de perfil com mesma lógica de confirmação por janelas (banda laranja só se alguma janela confirma, `only_1h` → risco)

## Notas da sessão (2026-03-15)

- Criada estrutura de specs para todas as 6 fases
- CLAUDE.md enxugado, detalhes movidos para `specs/`
- Revisão adversária dos pontos fracos, correções aplicadas
