# Relatório — Modelos Especialistas Pancada vs Prolongada

**Data:** 2026-05-20  
**Agente:** modelador-kimi (Kimi K2.6)  
**Script:** `notebooks/scripts/experiments/_especialistas_pancada_prolongada.py`  
**Baseline:** Benchmark V8 (leak-corrected, GradBoost, todas as features)

---

## 1. Objetivo

Testar se a separação em dois especialistas meteorológicos — **pancada** (pico, intensidade curta) e **prolongada/saturante** (acumulado, persistência) — produz um score combinado mais proporcional à intensidade da chuva do que o modelo único baseline V8.

---

## 2. Metodologia

### 2.1 Features por Especialista

| Especialista | Features principais | Lógica |
|---|---|---|
| **Pancada** | `pico_1h_lag1`, `max_day_lag1/2/3`, `horas_intensas_lag1`, `std_day_lag1`, `acc_6h_lag_9-12`, `n_chovendo_max_lag1`, `pico_vs_media`, `max_vs_media` | Captura picos de curta duração, concentração espacial e intensidade horária |
| **Prolongada** | `acum_7d`, `acum_30d`, `api_070/085/095`, `mean_day_lag1`, `max_day_lag1`, `n_chovendo_max_lag1`, `acc_24h_lag1`, `acc_48h_lag1`, `razao_7d_30d` | Captura saturação do solo, acumulados de longo prazo e persistência |

Features derivadas calculadas no script: `acc_24h_lag1`, `acc_48h_lag1`, `razao_7d_30d`, `pico_vs_media`, `max_vs_media`.

### 2.2 Alvo

Ambos os especialistas prevem o mesmo alvo binário do V8: `P(severidade >= 1)`. Isso garante comparabilidade direta de métricas (PR-AUC, Spearman) contra o baseline.

### 2.3 Modelo

GradientBoostingClassifier (`max_depth=2`, `n_estimators=200`, `learning_rate=0.05`) — idêntico ao baseline V8 para isolamento de variável.

### 2.4 Combinações Testadas

- `max(prob_pancada, prob_prolongada)`
- `mean_50_50`: média simples
- `mean_60_40`: 60% pancada + 40% prolongada
- `mean_40_60`: 40% pancada + 60% prolongada

### 2.5 Avaliação

- **PR-AUC** (discriminação evento vs não-evento)
- **Spearman ρ** entre score e `max_dia` (proporcionalidade com intensidade de chuva)
- **Curva score vs faixa de chuva** (0–5, 5–10, 10–20, 20–30, 30–50, 50–80, 80+ mm)
- **Recall / Precisão / F1** com threshold otimizado por F1 no treino (TSS)
- **Split temporal:** treino pré-T_CUT (75% train / 25% val para threshold), teste pós-T_CUT

---

## 3. Resultados

### 3.1 Métricas Agregadas (média das 4 bacias)

| Modelo | PR-AUC | Recall | Prec | F1 | Spearman ρ |
|---|---|---|---|---|---|
| **Baseline V8** | 0.149 | 0.311 | 0.128 | 0.168 | **0.212** |
| Pancada isolado | 0.133 | 0.225 | 0.142 | 0.168 | 0.225 |
| Prolongada isolado | 0.116 | 0.355 | 0.108 | 0.162 | 0.179 |
| **Comb max** | 0.146 | 0.376 | 0.205 | **0.255** | **0.272** |
| **Comb mean_50_50** | 0.148 | 0.366 | 0.216 | **0.256** | **0.275** |
| **Comb mean_60_40** | **0.152** | 0.322 | **0.224** | **0.253** | **0.279** |
| Comb mean_40_60 | 0.137 | 0.373 | 0.212 | 0.254 | 0.269 |

**Conclusão agregada:** A combinação **mean_60_40** oferece o melhor Spearman médio (**+0.067** vs baseline) e PR-AUC médio competitivo (**+0.003** vs baseline). O especialista isolado prolongada é sistematicamente inferior ao pancada.

### 3.2 Delta por Bacia vs Baseline V8

| Bacia | Combinação | Δ PR-AUC | Δ Spearman |
|---|---|---|---|
| **guarara** | max | **+0.036** | **+0.081** |
| guarara | mean_50_50 | +0.035 | +0.088 |
| guarara | **mean_60_40** | **+0.040** | **+0.097** |
| meninos | max | −0.092 | **+0.092** |
| meninos | mean_50_50 | −0.084 | +0.093 |
| meninos | mean_60_40 | −0.080 | **+0.096** |
| oratorio | max | +0.008 | **+0.050** |
| oratorio | mean_50_50 | +0.010 | +0.049 |
| oratorio | mean_60_40 | **+0.015** | +0.046 |
| tamanduatei | max | **+0.037** | +0.016 |
| tamanduatei | mean_50_50 | +0.037 | +0.018 |
| tamanduatei | mean_60_40 | +0.036 | **+0.028** |

**Destaques:**
- **Guarara** é a bacia mais beneficiada: ganhos consistentes em PR-AUC e Spearman (ΔSpearman até +0.097).
- **Meninos** ganha muito em proporcionalidade (+0.096 Spearman) mas perde discriminação (−0.080 PR-AUC). O especialista pancada isolado degrada fortemente (PR-AUC 0.057 vs baseline 0.173), indicando que a separação de features remove sinal útil para esta bacia pequena.
- **Oratorio** melhora em Spearman (+0.046 a +0.050) com leve ganho em PR-AUC.
- **Tamanduatei** melhora em PR-AUC (+0.036) e levemente em Spearman (+0.028).

### 3.3 Curva Score vs Faixa de Chuva (combinação max)

| Bacia | Faixa (mm) | N | Score Médio | Taxa Real Pos. | Delta |
|---|---|---|---|---|---|
| guarara | 0–5 | 326 | 0.156 | 0.009 | **+0.147** (superestima) |
| guarara | 5–10 | 60 | 0.206 | 0.033 | **+0.172** (superestima) |
| guarara | 10–20 | 32 | 0.199 | 0.844 | **−0.644** (subestima) |
| guarara | 20–30 | 6 | 0.143 | 1.000 | **−0.857** (subestima muito) |
| meninos | 0–5 | 343 | 0.084 | 0.006 | +0.079 |
| meninos | 5–10 | 48 | 0.104 | 0.000 | +0.104 |
| meninos | 10–20 | 30 | 0.118 | 0.167 | −0.049 |
| meninos | 20–30 | 3 | 0.128 | 1.000 | −0.872 |
| oratorio | 0–5 | 404 | 0.072 | 0.002 | +0.070 |
| oratorio | 5–10 | 60 | 0.106 | 0.017 | +0.089 |
| oratorio | 10–20 | 43 | 0.104 | 0.349 | −0.245 |
| oratorio | 20–30 | 6 | 0.108 | 1.000 | −0.892 |
| tamanduatei | 0–5 | 322 | 0.173 | 0.012 | +0.161 |
| tamanduatei | 5–10 | 58 | 0.216 | 0.034 | +0.182 |
| tamanduatei | 10–20 | 37 | 0.215 | 0.649 | −0.434 |
| tamanduatei | 20–30 | 7 | 0.160 | 1.000 | −0.840 |

**Diagnóstico:**
- O problema de **subestimação massiva em chuvas >10 mm persiste** em todas as bacias.
- Em **guarara**, o score na faixa 5–10 mm (0.206) é **maior** que na faixa 10–20 mm (0.199) e 20–30 mm (0.143). A curva não é monotônica crescente.
- Isso indica que mesmo a combinação de especialistas **não resolveu o viés conservador** do modelo para eventos extremos.

---

## 4. Diagnóstico: Por Que Ainda Há Subestimação?

1. **Desbalanceamento extremo:** 88–95% de negativos. O modelo aprende a dizer "não" para quase tudo.
2. **`max_depth=2`:** Muito restritivo para capturar interações não-lineares entre picos e acumulados.
3. **Threshold otimizado por F1:** Prioriza equilíbrio precisão/recall, não proporcionalidade com chuva. Thresholds altos comprimem scores.
4. **Poucos exemplos de >20 mm no treino:** O modelo pode nunca ter visto padrões suficientes de chuva extrema para associá-los a eventos.

---

## 5. Conclusões e Recomendações

### 5.1 Especialista que Funciona

- **Especialista Pancada** é sistematicamente superior ao Prolongada em Spearman (proporcionalidade) em 3 de 4 bacias.
- **Combinação mean_60_40** (60% pancada + 40% prolongada) oferece o melhor equilíbrio: Spearman médio **0.279** (+0.067 vs baseline), PR-AUC médio **0.152** (+0.003 vs baseline).
- **Combinação max** é útil operacionalmente: dispara alarme se qualquer perfil estiver presente, aumentando recall (0.376 médio vs 0.311 baseline).

### 5.2 Bacias Beneficiadas

| Bacia | Benefício principal | Magnitude |
|---|---|---|
| **Guarara** | Spearman + PR-AUC | ΔSpearman +0.097, ΔPR-AUC +0.040 |
| **Tamanduatei** | PR-AUC + Spearman leve | ΔPR-AUC +0.037, ΔSpearman +0.028 |
| **Oratorio** | Spearman | ΔSpearman +0.050, ΔPR-AUC +0.015 |
| **Meninos** | Spearman apenas | ΔSpearman +0.096, mas ΔPR-AUC −0.080 |

### 5.3 Limites Conhecidos

1. **Subestimação de cauda não foi resolvida:** chuvas >20 mm ainda recebem score de ~10–16% quando a taxa real de positivos é 100%.
2. **Meninos é instável com especialistas:** a separação de features remove sinal necessário para esta bacia pequena.
3. **Não-monotonicidade:** em guarara, score médio na faixa 5–10 mm > 10–20 mm > 20–30 mm.
4. **A abordagem não supera o baseline em todas as dimensões simultaneamente:** há trade-off entre proporcionalidade (Spearman) e discriminação (PR-AUC), especialmente em meninos.

### 5.4 Recomendação

- **NÃO substituir o champion V8** ainda. A combinação de especialistas deve ser tratada como **experimento complementar**.
- **Usar mean_60_40 em guarara e tamanduatei** para teste operacional controlado (A/B): estas bacias mostraram ganho consistente.
- **Investigar meninos separadamente:** a separação por perfil prejudica a discriminação. Manter baseline V8 para meninos até nova rodada.
- **Próximos passos sugeridos:**
  1. Aumentar `max_depth` para 4–6 e testar novamente com especialistas.
  2. Introduzir sample weights agressivos (sev 0→0.1, sev 1→1.0, sev 2→5.0, sev 3→20.0) para forçar sensibilidade à cauda.
  3. Avaliar regressão direta com loss de ordenação (ex: LambdaRank) em vez de classificação binária.

---

## 6. Artefatos Gerados

| Arquivo | Descrição |
|---|---|
| `notebooks/scripts/experiments/_especialistas_pancada_prolongada.py` | Script do experimento (isolado, não altera backend) |
| `notebooks/dados/results/especialistas_baseline.parquet` | Métricas do baseline V8 replicado |
| `notebooks/dados/results/especialistas_individual.parquet` | Métricas dos especialistas isolados |
| `notebooks/dados/results/especialistas_combinados.parquet` | Métricas das 4 combinações por bacia |
| `notebooks/dados/results/especialistas_faixas_max.parquet` | Estatísticas por faixa de chuva (comb max) |
| `notebooks/dados/results/especialistas_faixas_combinado_max.png` | Gráfico de barras score vs taxa real |
| `notebooks/dados/results/especialistas_scatter_guarara.png` | Scatter max_dia vs prob (guarara) |
| `notebooks/dados/results/especialistas_scatter_meninos.png` | Scatter max_dia vs prob (meninos) |
| `notebooks/dados/results/especialistas_scatter_oratorio.png` | Scatter max_dia vs prob (oratorio) |
| `notebooks/dados/results/especialistas_scatter_tamanduatei.png` | Scatter max_dia vs prob (tamanduatei) |
| `notebooks/dados/results/relatorio_especialistas_pancada_prolongada.md` | Este relatório |

---

*Relatório gerado automaticamente pelo subagente modelador-kimi.*
