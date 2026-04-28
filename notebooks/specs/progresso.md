# Progresso do Pipeline

## Fase ativa: 1/2 — chamados_exploratoria.py + pluviometria_exploratoria.py

**Status:** Notebooks refatorados e expandidos. Pronto para criar `chamados_por_bacia.py`.

**Próximo passo:** Criar `chamados_por_bacia.py` — revalidação dos chamados confirmados usando apenas estações da bacia (Passo 5 do plano).

**O que falta no pipeline:**
- `chamados_por_bacia.py` — reconfirmar chamados bacia a bacia com estações do `estacoes_bacia.json`; ver quais chamados caem
- Validação manual de datas sem chamados (TODO no notebook — busca por notícias)
- Export `chamados_enchente.parquet` com `confirmado_chuva_bacia`
- Export `datas_enchente_consolidadas.csv`

## Artefatos

| Artefato | Existe? |
|----------|---------|
| `dados/chamados_por_bacia.parquet` | Sim (chamados confirmados por chuva, qualquer estação) |
| `dados/estacoes_bacia.json` | Sim (estações relevantes por bacia, score ajustado) |
| `dados/chamados_enchente.parquet` | Não |
| `dados/datas_enchente_consolidadas.csv` | Não |
| `dados/cemaden_limpo.parquet` | Não |
| `dados/cemaden_diario_bacia.parquet` | Não |
| `dados/percentis_chuva.json` | Não |
| `dados/features_24h.parquet` | Não |
| `dados/target_por_bacia.parquet` | Não |

## Fases seguintes

| Fase | Status |
|------|--------|
| chamados_por_bacia.py | A criar |
| 2. pluviometria_exploratoria | Em progresso (AUC, mapa, estacoes_bacia.json) |
| 3. processamento_features | Não iniciada |
| 4. modelagem_classica | Não iniciada |
| 5. modelagem_temporal | Não iniciada |
| 6. forecast_integracao | Não iniciada |

## Notas da sessão (2026-04-07)

- Substituído filtro de outliers CEMADEN por `min_chamados` (ui.number, padrão 3, mín 0)
- Diadema removida do parquet CEMADEN; Mauá adicionada — 5,1M linhas, 4 municípios
- Filtro `municipio == "SANTO ANDRÉ"` removido da carga do CEMADEN (usa tudo)
- Export `chamados_por_bacia.parquet` agora usa `df_enchente_confirmado.filter(confirmado_chuva)` — apenas chamados confirmados por chuva
- Seção "dias suspeitos" simplificada: mostra todos os dias sem confirmação de chuva com callout de exclusão
- Seção "confirmados sem chamados" expandida: consolida 3 fontes externas com tolerância de ±3 dias; mostra fontes de cada evento; TODO de busca por notícias adicionado
- `pluviometria_exploratoria.py`: d0 por bacia (4 sliders, posicionados acima do radio de bacia); score ajustado com demérito Gaussiano por distância ao centróide; mapa mostra anel (score original) + círculo preenchido (score ajustado); limiar de score ajustado + texto resumido por bacia/município + botão salvar `estacoes_bacia.json`

## Notas da sessão (2026-03-16)

- Refatoração completa de performance e qualidade: Polars nativo em todo o notebook, Altair 6.0 sem `.to_pandas()`, células de constantes e `lims` separadas
- Filtro de outliers CEMADEN com `mo.ui.number` e stats de remoção
- Gráfico de perfil interativo: seleção por clique, janela 72h relativa ao chamado mais cedo, banda/risco cinza para chamados, banda/risco laranja para evento de chuva
- Lógica de `dt_ajustado`: pico de 1h dentro da melhor janela acumulada (1h/3h/6h) nas 72h anteriores
- Janelas de evento (`event_start`/`event_end`): expande do pico enquanto chuva ≥ limiar configurável, máx 6h por lado; `only_1h` → ponto único
- Tabela de dias suspeitos (>10 chamados 809.x sem confirmação) e seção "Alagamentos confirmados sem chamados"
