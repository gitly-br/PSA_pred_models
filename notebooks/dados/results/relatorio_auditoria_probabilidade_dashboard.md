# Relatório: Auditoria de Probabilidade para Dashboard

**Data:** 2026-05-20 11:35  
**Script:** `_auditoria_probabilidade_dashboard.py`

---

## 1. Objetivo

Determinar se existe candidato melhor que o baseline atual (V8 prob + display rescaling)
para uso no dashboard, em termos de **probabilidade/score operacional interpretável**.

## 2. Candidatos Avaliados

| Candidato | Descrição | Escala |
|-----------|-----------|--------|
| baseline_v8 | Baseline V8 prob k=1 (raw_proba do backend) | prob_bruta |
| combinador_mean_bruto | Combinador mean bruto (média scores normalizados) | score_0_1 |
| combinador_mean_calibrado | Combinador mean calibrado piecewise para serving | score_0_1 |
| classificador_cauda | Classificador cauda pesada (raw prob) | prob_bruta |
| especialistas_mean_60_40 | Reconstruído: 0.6*pancada_norm + 0.4*prolongada_norm | score_0_1 |
| combinador_max | Combinador max (referência) | score_0_1 |
| combinador_weighted | Combinador weighted (referência) | score_0_1 |

## 3. Métricas Agregadas (média global, teste)

| Candidato | PR-AUC | Spearman max_dia | Brier | %Baixo | %Moderado | %Alto | FP-Alto | Dyn Range |
|-----------|--------|------------------|-------|--------|-----------|-------|---------|-----------|
| baseline_v8               | 0.143 | 0.229 | 0.058 | 96.1% | 3.9% | 0.1% | 0.06% | 0.468 |
| combinador_mean_bruto     | 0.141 | 0.354 | 0.066 | 91.1% | 8.9% | 0.0% | 0.00% | 0.460 |
| combinador_mean_calibrado | 0.125 | 0.350 | 0.205 | 48.0% | 36.9% | 15.2% | 13.48% | 1.000 |
| classificador_cauda       | 0.122 | 0.184 | 0.107 | 79.3% | 15.6% | 5.0% | 4.47% | 0.891 |
| especialistas_mean_60_40  | 0.162 | 0.285 | 0.057 | 95.7% | 4.3% | 0.1% | 0.00% | 0.447 |
| combinador_max            | 0.126 | 0.276 | 0.252 | 15.9% | 72.0% | 12.2% | 10.97% | 0.818 |
| combinador_weighted       | 0.137 | 0.332 | 0.063 | 90.5% | 9.5% | 0.0% | 0.00% | 0.544 |

## 4. Comportamento por Faixa de Chuva (média global ponderada)

| Candidato | 0-5mm | 5-10mm | 10-20mm | 20-30mm | Delta(forte-leve) |
|-----------|-------|--------|---------|---------|-------------------|
| baseline_v8               | 0.094 | 0.124 | 0.130 | 0.124 | 0.015 |
| classificador_cauda       | 0.159 | 0.236 | 0.198 | 0.242 | 0.044 |
| combinador_max            | 0.456 | 0.562 | 0.534 | 0.558 | 0.049 |
| combinador_mean_bruto     | 0.143 | 0.205 | 0.200 | 0.239 | 0.065 |
| combinador_mean_calibrado | 0.332 | 0.500 | 0.491 | 0.589 | 0.173 |
| combinador_weighted       | 0.094 | 0.175 | 0.174 | 0.241 | 0.106 |
| especialistas_mean_60_40  | 0.080 | 0.118 | 0.119 | 0.095 | -0.004 |

## 5. Monotonicidade por Faixa de Chuva (média entre bacias)

| Candidato | rho_mono | Inversoes | Delta(forte-leve) | Score leve | Score forte |
|-----------|----------|-----------|-------------------|------------|-------------|
| baseline_v8               | 0.500 | 0.75 | 0.010 | 0.110 | 0.119 |
| classificador_cauda       | 0.650 | 0.75 | 0.025 | 0.198 | 0.223 |
| combinador_max            | 0.600 | 1.00 | 0.031 | 0.506 | 0.537 |
| combinador_mean_bruto     | 0.750 | 0.75 | 0.052 | 0.174 | 0.226 |
| combinador_mean_calibrado | 0.750 | 0.75 | 0.160 | 0.416 | 0.576 |
| combinador_weighted       | 0.700 | 1.00 | 0.088 | 0.134 | 0.222 |
| especialistas_mean_60_40  | 0.250 | 1.25 | -0.005 | 0.099 | 0.095 |

## 6. Casos Críticos (Top 10 por tipo/candidato)


### baseline_v8
| Data | Bacia | max_dia | Severidade | Score | Tipo |
|------|-------|---------|------------|-------|------|
| 2024-03-10 00:00:00 | guarara | 5.1 | 0 | 0.542 | leve_score_alto |
| 2024-03-18 00:00:00 | guarara | 3.5 | 0 | 0.556 | leve_score_alto |
| 2024-03-19 00:00:00 | guarara | 0.2 | 0 | 0.529 | leve_score_alto |
| 2023-02-14 00:00:00 | oratorio | 6.8 | 0 | 0.605 | leve_score_alto |
| 2023-12-24 00:00:00 | tamanduatei | 1.2 | 0 | 0.551 | leve_score_alto |
| 2024-02-15 00:00:00 | tamanduatei | 2.4 | 0 | 0.560 | leve_score_alto |
| 2024-02-25 00:00:00 | tamanduatei | 0.4 | 0 | 0.643 | leve_score_alto |
| 2024-02-26 00:00:00 | tamanduatei | 0.6 | 3 | 0.534 | leve_score_alto |
| 2024-03-18 00:00:00 | tamanduatei | 3.5 | 0 | 0.585 | leve_score_alto |
| 2024-03-19 00:00:00 | tamanduatei | 0.2 | 0 | 0.563 | leve_score_alto |

### classificador_cauda
| Data | Bacia | max_dia | Severidade | Score | Tipo |
|------|-------|---------|------------|-------|------|
| 2023-11-02 00:00:00 | guarara | 0.4 | 0 | 0.647 | leve_score_alto |
| 2023-11-04 00:00:00 | guarara | 1.6 | 0 | 0.683 | leve_score_alto |
| 2023-11-05 00:00:00 | guarara | 0.2 | 0 | 0.701 | leve_score_alto |
| 2023-11-08 00:00:00 | guarara | 0.2 | 0 | 0.652 | leve_score_alto |
| 2023-11-09 00:00:00 | guarara | 3.0 | 0 | 0.539 | leve_score_alto |
| 2023-11-10 00:00:00 | guarara | 0.2 | 0 | 0.766 | leve_score_alto |
| 2023-11-24 00:00:00 | guarara | 0.6 | 0 | 0.526 | leve_score_alto |
| 2023-12-05 00:00:00 | guarara | 0.2 | 0 | 0.527 | leve_score_alto |
| 2023-12-24 00:00:00 | guarara | 0.4 | 0 | 0.894 | leve_score_alto |
| 2023-12-26 00:00:00 | guarara | 0.2 | 0 | 0.527 | leve_score_alto |

### combinador_max
| Data | Bacia | max_dia | Severidade | Score | Tipo |
|------|-------|---------|------------|-------|------|
| 2023-11-02 00:00:00 | guarara | 0.4 | 0 | 0.649 | leve_score_alto |
| 2023-11-04 00:00:00 | guarara | 1.6 | 0 | 0.685 | leve_score_alto |
| 2023-11-05 00:00:00 | guarara | 0.2 | 0 | 0.703 | leve_score_alto |
| 2023-11-08 00:00:00 | guarara | 0.2 | 0 | 0.654 | leve_score_alto |
| 2023-11-09 00:00:00 | guarara | 3.0 | 0 | 0.540 | leve_score_alto |
| 2023-11-10 00:00:00 | guarara | 0.2 | 0 | 0.769 | leve_score_alto |
| 2023-11-18 00:00:00 | guarara | 0.6 | 0 | 0.520 | leve_score_alto |
| 2023-11-19 00:00:00 | guarara | 5.9 | 0 | 0.553 | leve_score_alto |
| 2023-11-21 00:00:00 | guarara | 0.2 | 0 | 0.589 | leve_score_alto |
| 2023-11-22 00:00:00 | guarara | 3.4 | 0 | 0.798 | leve_score_alto |

### combinador_mean_bruto
| Data | Bacia | max_dia | Severidade | Score | Tipo |
|------|-------|---------|------------|-------|------|
| 2024-01-19 00:00:00 | guarara | 9.8 | 0 | 0.531 | leve_score_alto |
| 2024-01-20 00:00:00 | guarara | 5.5 | 0 | 0.550 | leve_score_alto |
| 2024-02-21 00:00:00 | guarara | 9.9 | 3 | 0.506 | leve_score_alto |
| 2024-02-25 00:00:00 | guarara | 0.2 | 0 | 0.552 | leve_score_alto |
| 2024-03-18 00:00:00 | guarara | 3.5 | 0 | 0.515 | leve_score_alto |
| 2023-02-17 00:00:00 | oratorio | 7.9 | 0 | 0.520 | leve_score_alto |
| 2024-01-12 00:00:00 | tamanduatei | 6.3 | 0 | 0.547 | leve_score_alto |
| 2024-01-19 00:00:00 | tamanduatei | 9.8 | 0 | 0.558 | leve_score_alto |
| 2024-01-20 00:00:00 | tamanduatei | 6.1 | 0 | 0.530 | leve_score_alto |
| 2024-02-21 00:00:00 | tamanduatei | 9.9 | 3 | 0.522 | leve_score_alto |

### combinador_mean_calibrado
| Data | Bacia | max_dia | Severidade | Score | Tipo |
|------|-------|---------|------------|-------|------|
| 2023-11-01 00:00:00 | guarara | 1.4 | 0 | 0.609 | leve_score_alto |
| 2023-11-02 00:00:00 | guarara | 0.4 | 0 | 0.535 | leve_score_alto |
| 2023-11-04 00:00:00 | guarara | 1.6 | 0 | 0.700 | leve_score_alto |
| 2023-11-05 00:00:00 | guarara | 0.2 | 0 | 0.594 | leve_score_alto |
| 2023-11-08 00:00:00 | guarara | 0.2 | 0 | 0.518 | leve_score_alto |
| 2023-11-09 00:00:00 | guarara | 3.0 | 0 | 0.544 | leve_score_alto |
| 2023-11-10 00:00:00 | guarara | 0.2 | 0 | 0.744 | leve_score_alto |
| 2023-11-16 00:00:00 | guarara | 4.3 | 0 | 0.605 | leve_score_alto |
| 2023-11-17 00:00:00 | guarara | 0.2 | 0 | 0.607 | leve_score_alto |
| 2023-11-18 00:00:00 | guarara | 0.6 | 0 | 0.650 | leve_score_alto |

### combinador_weighted
| Data | Bacia | max_dia | Severidade | Score | Tipo |
|------|-------|---------|------------|-------|------|
| 2023-11-28 00:00:00 | guarara | 3.9 | 0 | 0.505 | leve_score_alto |
| 2024-01-11 00:00:00 | guarara | 10.0 | 0 | 0.518 | leve_score_alto |
| 2024-01-12 00:00:00 | guarara | 6.3 | 0 | 0.618 | leve_score_alto |
| 2024-01-19 00:00:00 | guarara | 9.8 | 0 | 0.590 | leve_score_alto |
| 2024-01-20 00:00:00 | guarara | 5.5 | 0 | 0.643 | leve_score_alto |
| 2024-01-21 00:00:00 | guarara | 9.8 | 0 | 0.516 | leve_score_alto |
| 2024-02-21 00:00:00 | guarara | 9.9 | 3 | 0.558 | leve_score_alto |
| 2024-02-25 00:00:00 | guarara | 0.2 | 0 | 0.536 | leve_score_alto |
| 2024-02-28 00:00:00 | guarara | 1.2 | 0 | 0.512 | leve_score_alto |
| 2024-03-18 00:00:00 | guarara | 3.5 | 0 | 0.524 | leve_score_alto |

### especialistas_mean_60_40
| Data | Bacia | max_dia | Severidade | Score | Tipo |
|------|-------|---------|------------|-------|------|
| 2024-02-25 00:00:00 | guarara | 0.2 | 0 | 0.565 | leve_score_alto |
| 2024-03-10 00:00:00 | guarara | 5.1 | 0 | 0.500 | leve_score_alto |
| 2025-04-01 00:00:00 | guarara | 0.2 | 3 | 0.822 | leve_score_alto |
| 2025-04-01 00:00:00 | meninos | 0.2 | 2 | 0.534 | leve_score_alto |
| 2024-02-03 00:00:00 | tamanduatei | 0.4 | 0 | 0.617 | leve_score_alto |
| 2024-02-15 00:00:00 | tamanduatei | 2.4 | 0 | 0.520 | leve_score_alto |
| 2024-02-25 00:00:00 | tamanduatei | 0.4 | 0 | 0.617 | leve_score_alto |
| 2024-03-18 00:00:00 | tamanduatei | 3.5 | 0 | 0.630 | leve_score_alto |
| 2025-04-01 00:00:00 | tamanduatei | 0.2 | 3 | 0.620 | leve_score_alto |
| 2025-04-20 00:00:00 | tamanduatei | 5.5 | 0 | 0.595 | leve_score_alto |

## 7. Matriz de Decisão

| Candidato | Decisão | Score leve | Score forte | FP-Alto | Principais Motivos |
|-----------|---------|------------|-------------|---------|--------------------|
| baseline_v8               | descartar              | 0.110 | 0.119 | 0.06% | baseline conhecido: inversoes, subestimacao severa, inferior aos candidatos |
| combinador_mean_bruto     | usar_shadow            | 0.174 | 0.226 | 0.00% | melhor que baseline em Spearman e mono, mas resolucao na cauda ainda fraca |
| combinador_mean_calibrado | descartar              | 0.416 | 0.576 | 13.48% | alarmismo excessivo (13.5% nao-eventos classificados ALTO); score base elevado (0.416 em chuva leve) |
| classificador_cauda       | validar_mais           | 0.198 | 0.223 | 4.47% | Spearman baixo; separacao forte/leve fraca; alarmismo |
| especialistas_mean_60_40  | descartar              | 0.099 | 0.095 | 0.00% | inversoes frequentes ou delta_forte_leve negativo |
| combinador_max            | descartar              | 0.506 | 0.537 | 10.97% | alarmismo excessivo (11.0% nao-eventos classificados ALTO); score base elevado (0.506 em chuva leve) |
| combinador_weighted       | usar_shadow            | 0.134 | 0.222 | 0.00% | melhor que baseline em Spearman e mono, mas resolucao na cauda ainda fraca |

## 8. Ranking Final (Dashboard — critério operacional)

Score composto:
- Spearman max_dia (30%)
- Monotonicidade por faixa (25%)
- Delta forte-leve (25%)
- Controle de alarmismo FP-Alto (20%)

Candidatos descartados por alarmismo ou inversoes recebem penalidade de 50% no score.

| Rank | Candidato | Score Dashboard | Decisão |
|------|-----------|----------------|---------|
| 1 | combinador_mean_bruto     | 0.837 | usar_shadow |
| 2 | combinador_weighted       | 0.827 | usar_shadow |
| 3 | combinador_mean_calibrado | 0.397 | descartar |
| 4 | classificador_cauda       | 0.379 | validar_mais |
| 5 | combinador_max            | 0.215 | descartar |
| 6 | baseline_v8               | 0.213 | descartar |
| 7 | especialistas_mean_60_40  | 0.189 | descartar |

## 9. Recomendação Final

**Candidato recomendado para shadow: `combinador_mean_bruto`**

- Decisão: `usar_shadow`
- Score composto dashboard: 0.837
- Spearman max_dia: 0.354
- Monotonicidade faixa: 0.750
- Delta forte-leve: 0.052
- FP alto (alarmismo): 0.00%
- Score médio em chuva leve: 0.174
- Score médio em chuva forte: 0.226

Este candidato é objetivamente superior ao baseline em proporcionalidade e monotonicidade,
mas ainda subestima eventos extremos (resolucao de cauda insuficiente).
Recomenda-se rodar em paralelo ao baseline (shadow) por 30-60 dias antes de promover.

## 10. Problema do Backend (runner.py)

O backend atual (`floodcast/runner.py`) retorna:
- `raw_proba = model.predict_proba(X)[0][predict_value]` — prob da **classe predita**, não do evento.
- `display_probability` faz rescale threshold-based que distorce a escala.

Isso significa que a `proba` enviada ao dashboard **não é uma probabilidade
operacional interpretável** de risco. O score calibrado (`risk_score_raw_mean_serving`)
é uma alternativa objetivamente superior em escala, mas **foi descartado nesta auditoria
por alarmismo excessivo** (13.5% dos não-eventos classificados como ALTO).

**Recomendação arquitetural**: a probabilidade enviada ao dashboard deve vir de um
score operacional calibrado e auditado (como este processo), não de `raw_proba` +
rescale threshold-based. Qualquer candidato aprovado deve passar por esta auditoria
antes de ser exposto na API.

## 11. Limitações e Riscos Conhecidos

- Poucos eventos >30mm no teste; comportamento na cauda é incerto.
- O calibrador piecewise foi ajustado até 2024-07-01; drift temporal pode degradar.
- Especialistas mean_60_40 são reconstruídos a partir de componentes normalizados;
  um modelo combinado treinado end-to-end pode ter desempenho diferente.
- Classificador_cauda tem alarmismo moderado (4.5% fp_alto) e Spearman baixo;
  não é candidato viável para dashboard sem ajuste de threshold.

## 12. Arquivos Gerados

- `auditoria_probabilidade_dashboard.parquet` — métricas agregadas por candidato
- `auditoria_probabilidade_dashboard_faixas.parquet` — curva por faixa de chuva
- `auditoria_probabilidade_dashboard_criticos.parquet` — datas críticas auditadas
- `relatorio_auditoria_probabilidade_dashboard.md` — este relatório
