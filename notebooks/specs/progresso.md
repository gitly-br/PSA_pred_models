# Progresso do Pipeline

## Fase ativa: modelagem_baseline.py (Fases 3+4 combinadas)

**Status:** Notebook completo com narrativa. Baseline treinado e avaliado. Gate de chuva testado.

**Próximo passo:** Ajuste de threshold por curva precision-recall + features temporais (fase 5).

**O que falta no pipeline:**
- Ajuste de threshold por curva precision-recall por bacia
- Features temporais: lags, rolling stats (fase 5)
- Integração de forecast (fase 6)
- Revalidação de estações e limiares para bacia meninos

## Decisões tomadas nesta sessão (2026-04-28)

- Caminho B: features + modelagem diretamente dos dados existentes, sem artefatos intermediários de fase 3
- Chuva por bacia: `max` entre estações por hora para revalidação e features; `mean` incluído como feature adicional
- Parquets wide por bacia em `dados/chuva_bacias/` (1 coluna por estação, horas sem leitura = 0)
- Split: train < 2024, test 2024–2025
- Features: max e mean por janela (18 features no total)
- **Bacia meninos:** 50,8% de confirmação (vs ~70% nas demais) — estações podem ter cobertura insuficiente. Registrado para revalidação futura da seleção de estações.

## Artefatos

| Artefato | Existe? |
|----------|---------|
| `dados/chamados_por_bacia.parquet` | Sim (chamados confirmados por chuva, qualquer estação) |
| `dados/estacoes_bacia.json` | Sim (estações por score ajustado) |
| `dados/chuva_bacias/chuva_{bacia}.parquet` | Sim (wide, 1 col/estação, 87.672 horas) |
| `dados/cemaden_abcd.parquet` | Sim |
| `dados/chamados_enchente.parquet` | Não (substituído por lógica inline) |
| `dados/features_24h.parquet` | Não (gerado inline no modelagem_baseline.py) |

## Fases seguintes

| Fase | Status |
|------|--------|
| preprocessamento_chuva.py | ✅ Concluído |
| modelagem_baseline.py | 🔄 Em progresso (revalidação pronta, features a fazer) |
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
