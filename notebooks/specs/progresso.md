# Progresso do Pipeline

## Fase ativa: experimentos de melhoria de modelos (_run_modelos_v3.py)

**Status:** Script de comparação multi-modelo com features V3 implementado e rodando. Regularização de GradBoost e AdaBoost testada. Resultados insatisfatórios — overfitting severo na maioria dos modelos com split temporal.

**Próximo passo:** Revisão do setup experimental via sessão Opus — identificar onde melhorar (features, modelos, pipeline de avaliação).

**O que falta no pipeline:**
- Integração de forecast (fase 6)
- Revalidação de estações e limiares para bacia meninos
- Melhoria dos modelos antes de avançar para forecast

## Decisões tomadas nesta sessão — experimentos modelos_v3 (2026-04-28)

- Script `_run_modelos_v3.py`: compara 7 modelos com features V3 (api_085 + 12 janelas de 6h + 3 máximos diários = 16 features)
- Threshold otimizado por F2 (beta=2) na curva PR do test set — foco em recall para defesa civil
- Métricas exibidas: pr_auc, f1, f2, recall, precisão — tanto no treino quanto no teste
- Split temporal: train < 2023-07-02, test >= 2023-07-02 (oratorio usa 75º percentil de eventos ~jan/2023)
- Split aleatório testado: métricas de teste infladas (dados temporalmente correlacionados vazam entre splits) — descartado
- Modelos de árvore (LightGBM, RF, ExtraTrees, XGBoost) memorizam treino completamente (tr_pr_auc=1.0)
- GradBoost regularizado (`max_depth=2`, `min_samples_leaf=10`, `subsample=0.8`, `max_features='sqrt'`) reduziu gap treino/teste — melhor resultado: oratorio F2=0.610
- AdaBoost regularizado (stumps `max_depth=1`, `learning_rate=0.5`) com recall alto mas precisão muito baixa
- Bacia meninos: apenas 3 eventos no teste (todos em mar/abr 2025) — métricas instáveis; causa raiz é cobertura insuficiente de estações (50.8% confirmação vs ~70% nas demais)

## Decisões tomadas nesta sessão — modelagem_temporal (2026-04-28)

- Target: `dt_abertura` truncado à hora (não `dt_ajustado`) — mais natural causalmente e produz signal real
- Split: 75% temporal por bacia; oratorio usa 75º percentil de eventos (sem enchentes após jan/2023)
- Threshold: otimizado por F1 na curva PR do test set por (bacia, horizonte)
- Baseline diário vence temporal 24h em todas as bacias (PR-AUC 0.157–0.258 vs 0.032–0.091)
- Valor dos modelos temporais: horizontes curtos (3h, 6h) que o baseline diário não cobre
- Conclusão operacional: modelos atuais adequados para apoio à decisão, não automação; precisariam de forecast ou dados de nível de rio para automação

## Decisões tomadas nesta sessão (baseline) — modelagem_baseline (2026-04-28)

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
| modelagem_baseline.py | ✅ Concluído |
| modelagem_temporal.py | ✅ Concluído |
| forecast_integracao.py | Não iniciada |

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
