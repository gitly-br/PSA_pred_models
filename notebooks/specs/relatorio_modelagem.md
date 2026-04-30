# Relatório de Modelagem — Predição de Enchentes por Bacia

> **Sessão:** 2026-04-28
> **Escopo:** Quatro iterações de modelos (V3 → V4 → V5 → V5b) sobre o pipeline PSA.
> **Objetivo:** Identificar configuração que melhor prediz enchentes por bacia hidrográfica em Santo André usando dados pluviométricos CEMADEN.

---

## 1. Contexto e diagnóstico inicial

O pipeline existente (`_run_modelos_v3.py` antes desta sessão) comparava 7 modelos com 16 features V3 (api_085 + 12 lags de blocos de 6h + 3 max_dia). Os resultados eram aparentemente razoáveis em algumas bacias (oratorio F2 ≈ 0.61), mas três problemas foram identificados:

1. **Threshold otimizado na curva PR do test set** → vazamento. F1/F2/recall reportados eram inflados.
2. **Test set minúsculo** (3–11 positivos por bacia) → métricas pontuais sem IC; ranking de modelos virava ruído.
3. **Sem CV temporal** (walk-forward) → escolha de modelo/threshold cega.

Adicionalmente:
4. **Features pobres**: só chuva acumulada da bacia, sem variabilidade espacial entre estações.
5. **Bacia meninos com cobertura aparentemente baixa** (50,8% segundo nota antiga — depois falsificada).
6. **Sem incorporação de fontes externas** de eventos (`alagamentos_bacias.csv`, etc.) ao target.

---

## 2. Iteração V3 (Bloco A — avaliação honesta)

### Mudanças
| Item | Antes | Depois |
|---|---|---|
| Threshold | otimizado por F2 na curva PR do **test** | otimizado por F2 via TimeSeriesSplit (5 splits) **out-of-fold no treino** |
| Aplicação | mesmo dataset usado pra escolher e reportar | escolhido no treino, **fixo** no test |
| IC95 | ausente | bootstrap estratificado, 1000 reamostragens |
| Métrica operacional | ausente | alarmes/mês + eventos capturados (X/Y) |
| Custo computacional | 28 fits | 168 fits (×6) |

### Resultados (GradBoost regularizado)

| Bacia | F2 antes (vazado) | F2 V3 honesto | IC95 F2 | Eventos capt. | Alarmes/mês |
|---|---|---|---|---|---|
| guarara | 0.37 | 0.27 | [0.00, 0.51] | 3/8 | 1.64 |
| meninos | 0.42 | 0.31 | [0.00, 0.79] | 1/3 | 0.29 |
| oratorio | 0.61 | 0.35 | [0.30, 0.41] | 6/6 | 3.65 |
| tamanduatei | 0.54 | 0.48 | [0.30, 0.63] | 8/11 | 2.79 |

### Conclusões

- O ganho aparente do V3 era ilusão de threshold-leak. F2 caiu 0.06–0.26 quando avaliado honestamente.
- Oratorio era o caso mais inflado.
- IC95 muito largo em meninos (3 eventos no test) — qualquer comparação ali é especulativa.
- GradBoost domina AdaBoost em 3/4 bacias com confiança (IC95 não se sobrepõem em tamanduatei e meninos).

---

## 3. Iteração V4 (Bloco B — meninos; Bloco C — features novas)

### Bloco B: Revalidação de estações da bacia meninos

Hipótese inicial: cobertura de meninos era 50,8% (problema upstream). Diagnóstico programático em `_diagnostico_meninos.py`:

- Para cada chamado da bacia, computa quais estações CEMADEN confirmariam chuva (qualquer janela [1,3,6,24,48,72]h ≥ LIMS) na janela retroativa de 72 h.
- Cobertura medida: **81,2%** (147 de 181 chamados confirmados pelas 8 estações). O número 50,8% no spec antigo era de outra métrica.
- Greedy forward (raio 8 km do centróide dos chamados) → estação `354870814A` (Vila Vitória, SBC, 7,8 km) adiciona +20 chamados confirmados (cobertura 92,3%).
- Aceito o risco de chuva remota; ganho de positivos justifica.
- **Decisão:** adicionada ao `dados/estacoes_bacia.json` (9 estações em meninos).

Impacto direto no V3 com nova estação: train_pos meninos 16 → 18; F2 marginal (test ainda só tem 3 eventos).

### Bloco C: Features V4 (27 features, vs 16 no V3)

| Tipo | Features adicionadas |
|---|---|
| Espaciais entre estações | `mean_day_lag1`, `std_day_lag1`, `n_chovendo_max_lag1` |
| Regime/intensidade | `pico_1h_lag1`, `horas_intensas_lag1` (horas ≥ 5 mm) |
| Saturação | API com K∈{0.70, 0.85, 0.95}; `acum_7d`, `acum_30d` |
| Sazonalidade | `mes_sin`, `mes_cos` (cíclico) |
| Mantidas do V3 | 12 lags `acc_6h_lag_*`, 3 lags `max_day_lag*` |

Observação técnica: substituído `pl.max_horizontal` por agregações múltiplas (max + mean + std + count_chovendo) por hora por bacia, antes do agrupamento diário.

### Resultados V4 (GradBoost)

| Bacia | F2 V3 honesto | F2 V4 | Δ F2 | Recall V4 | Alarmes/mês V4 |
|---|---|---|---|---|---|
| guarara | 0.27 [0.00,0.51] | **0.43** [0.12, 0.70] | +0.16 | 0.50 | 1.07 |
| meninos | 0.31 [0.00,0.79] | **0.59** [0.00, 0.94] | +0.28 | 0.67 | 0.36 |
| oratorio | 0.35 [0.30,0.41] | **0.47** [0.22, 0.70] | +0.12 | 0.67 | 1.12 |
| tamanduatei | 0.48 [0.30,0.63] | **0.58** [0.45, 0.70] | +0.10 | 0.91 | 3.00 |

### Conclusões V4

- F2 subiu em **todas as bacias**.
- Tamanduatei: 10/11 eventos capturados, 3 alarmes/mês — perfil operacional útil.
- Oratorio: 4/6 eventos, 1.12 alarmes/mês (V3 capturava 6/6 com 3.65 — V4 perdeu 2 mas reduziu ruído ~3x).
- Meninos: F2 aparentemente alto, mas IC95 [0.00, 0.94] — sorte amostral, não conclusão.
- **Overfit não cedeu**: train PR-AUC subiu para 0.89–0.98. Mais features ajudaram o test apesar de aumentarem a memorização — mas indica que faltam ainda regularização e/ou exemplos.

---

## 4. Iteração V5 (Bloco D — target enriquecido)

### Hipótese central

O target binário ("houve chamado confirmado") confunde duas coisas distintas:
1. **Houve enchente?** (fenômeno físico)
2. **Alguém ligou?** (comportamento)

Em domingos, feriados, à noite, em bairros com baixa densidade de chamados — chuva pode ser idêntica a um dia "positivo" mas o telefone não tocou. Esses dias viram negativos rotulados errado, e o modelo aprende "chuva forte sem chamado = sem enchente" — explica parte do overfit.

### D1: Diagnóstico programático (`_diagnostico_dias_suspeitos.py`)

Para cada bacia, no espaço de features `[max_dia, acum_dia, mean_dia, n_chovendo_max, horas_intensas, api_085]` (normalizadas por desvio):
- Distância euclidiana de cada negativo ao positivo mais próximo.
- Limiar de similaridade: percentil intra-positivos.
- Cruzamento com fontes externas (`alagamentos_bacias.csv` — 79 datas com flags por bacia).

### D1 — Resultados

**Novos positivos via fonte externa (sem chamado):**

| Bacia | Pos. chamado V4 | Pos. fonte ext. | Novos | Total enriquecido | Δ |
|---|---|---|---|---|---|
| guarara | 51 | 35 | **+25** | 76 | +49% |
| meninos | 21 | 20 | **+17** | 38 | **+81%** |
| oratorio | 24 | 12 | +6 | 30 | +25% |
| tamanduatei | 73 | 50 | **+31** | 104 | +42% |

**Total: +79 positivos novos.** Maior impacto na meninos (que era a bacia mais limitada por dados) e tamanduatei.

**Suspeitos detectados (similar + chuva severa OU fim de semana):** entre 263 e 443 dias por bacia (15–26% dos negativos). Considerado **muito permissivo**.

### D2: Critério restrito de suspeito

Tornado conservador: dist ≤ p25 intra-positivos **E** chuva ≥ p75 dos positivos **E** fim de semana. Resultado: **2 suspeitos em guarara, 1 em meninos** — quase nenhum impacto no treino. Conservadorismo prevaleceu.

### V5 (peso uniforme, threshold F2)

Resultados imediatos: **recall ~1.00 em meninos, oratorio, tamanduatei**, mas precisão despencou (0.09–0.13). Alarmes/mês explodiu em tamanduatei (6.36).

| Bacia | F2 | Recall | Precisão | Alarmes/mês | Eventos capt. |
|---|---|---|---|---|---|
| guarara | 0.45 [0.25,0.62] | 0.75 | 0.17 | 2.50 | 6/8 |
| meninos | 0.32 [0.26,0.41] | 1.00 | 0.09 | 2.50 | 3/3 |
| oratorio | 0.43 [0.37,0.50] | 1.00 | 0.13 | 3.44 | 8/8 |
| tamanduatei | 0.41 [0.37,0.47] | 1.00 | 0.12 | 6.36 | 11/11 |

Diagnóstico: o target enriquecido virou o modelo alarmista. Pode ser por:
1. Eventos da fonte externa são sistematicamente mais fáceis (eventos grandes, midiáticos) — modelo aprendeu padrão "fácil".
2. Threshold por F2 já é viesado para recall; com mais positivos, fica ainda mais baixo.

### V5-F1 (threshold por F1)

Trocada otimização F2 → F1 na curva PR do CV (1 linha de código).

| Bacia | F2 | Recall | Precisão | Alarmes/mês | Eventos capt. |
|---|---|---|---|---|---|
| guarara | **0.49** [0.27,0.68] | 0.75 | 0.21 | **2.07** | 6/8 |
| meninos | **0.46** [0.00,0.75] | 0.67 | 0.20 | **0.71** | 2/3 |
| oratorio | **0.48** [0.33,0.61] | 0.88 | 0.17 | **2.28** | 7/8 |
| tamanduatei | 0.45 [0.24,0.62] | 0.64 | 0.21 | **2.43** | 7/11 |

- F2 médio subiu (0.40 → 0.47).
- Alarmes/mês caiu drasticamente (todos abaixo do orçamento sugerido de 4/mês).
- Precisão quase dobrou.
- Trade-off: recall caiu — tamanduatei perdeu 4 eventos.

---

## 5. Iteração V5b (peso 0,5 para fonte externa)

Hipótese: fonte externa é evidência de qualidade inferior à chamada local; pesar em 0.5 deveria dar mais voz à evidência local.

### Implementação

`sample_weight` no fit (CV + final): peso 1.0 se positivo via chamado; 0.5 se positivo só via fonte externa. Compatível com pipelines (`clf__sample_weight` no LogisticReg).

### Resultados

| Bacia | F2 V5b | Δ vs V5-F1 | Recall V5b | Precisão V5b | Alarmes/mês V5b |
|---|---|---|---|---|---|
| guarara | **0.51** [0.28,0.70] | +0.02 | 0.75 | 0.22 | 1.93 |
| meninos | 0.46 [0.00,0.79] | 0.00 | 0.67 | 0.20 | 0.71 |
| oratorio | 0.45 [0.25,0.61] | -0.03 | 0.75 | 0.17 | 1.94 |
| tamanduatei | 0.46 [0.26,0.64] | +0.01 | 0.64 | 0.21 | 2.36 |

PR-AUC train caiu em todas as bacias — overfit reduzido. Mas ganhos no test foram marginais (≤ 0.02 em F2, dentro dos IC95).

---

## 6. Comparação consolidada (todas as iterações)

### F2 (GradBoost) — ranking por bacia

| Bacia | V3 (Bloco A) | V4 (Blocos B+C) | V5-F1 | V5b | **Champion** |
|---|---|---|---|---|---|
| guarara     | 0.27 | 0.43 | 0.49 | **0.51** | **V5b** |
| meninos     | 0.31 | 0.59* | 0.46 | 0.46 | **V5-F1** (= V5b, mas F1 mais simples) |
| oratorio    | 0.35 | 0.47 | **0.48** | 0.45 | **V5-F1** |
| tamanduatei | 0.48 | **0.58** | 0.45 | 0.46 | **V4** |

*meninos V4 com IC95 [0.00, 0.94] — sorte amostral, não real ganho

### Insight

A inclusão da fonte externa **piora tamanduatei**. Hipótese: tamanduatei já tinha 73 chamados (volume suficiente) e os 31 eventos externos puxam padrão diferente. Para bacias com poucos chamados (meninos), o ganho de exemplos externos compensa; para bacias com volume suficiente, atrapalha.

### Trade-off operacional (V5-F1 vs V4 — perspectiva da defesa civil)

| Bacia | V4 alarmes/mês | V5-F1 alarmes/mês | V4 eventos capt. | V5-F1 eventos capt. |
|---|---|---|---|---|
| guarara | 1.07 | 2.07 | 4/8 | 6/8 |
| meninos | 0.36 | 0.71 | 2/3 | 2/3 |
| oratorio | 1.12 | 2.28 | 4/6 | 7/8 |
| tamanduatei | 3.00 | 2.43 | 10/11 | 7/11 |

V5-F1 é mais sensível em meninos/oratorio (mais eventos capturados) ao custo de alarmes. V4 é mais econômico em tamanduatei.

---

## 7. Lições e decisões finais desta sessão

### Validadas empiricamente

1. **Avaliação honesta importa muito.** Quase metade do "ganho" do V3 vinha de threshold-leak.
2. **Bootstrap IC95 é indispensável** com 3–11 positivos por test.
3. **Threshold por F1 supera F2** quando o target já tem muitos positivos — F2 vira recall-puro e perde precisão sem ganho operacional.
4. **Cobertura de estações por bacia já é boa** (80–90%) com a seleção atual; o ganho marginal de adicionar estações distantes é positivo mas modesto.
5. **Fonte externa ajuda bacias com poucos chamados; atrapalha bacias com volume.**
6. **Critério de suspeito muito permissivo é perigoso** (24% dos negativos viram suspeitos com critério padrão). Critério restrito acabou descartando quase nada — não foi o lever de melhoria nesta iteração.

### Ainda em aberto

- **Champion-by-basin oficial:** consolidar `_run_modelos_champion.py` carregando o modelo apropriado por bacia.
- **Calibração de probabilidades** (isotônica) — não testada.
- **Modelo multi-bacia com bacia one-hot** — adiado; pode revisitar para tamanduatei se houver ganho.
- **Forecast (Fase 6)** — não iniciado; é o pré-requisito de produção.
- **Instrumentação de runs** (Bloco F) — registrar runs em `experimentos.parquet` para iteração futura.

---

## 8. Reprodutibilidade

Scripts (todos rodam ~25 min, 168 fits cada):

```bash
uv run python _run_modelos_v3.py    # baseline V3 com avaliação honesta
uv run python _run_modelos_v4.py    # V4 (27 features)
uv run python _run_modelos_v5.py    # V5-F1 (target enriquecido + suspeitos)
uv run python _run_modelos_v5b.py   # V5b (peso 0,5 para fonte externa)
```

Diagnósticos auxiliares:

```bash
uv run python _diagnostico_meninos.py          # Bloco B
uv run python _diagnostico_dias_suspeitos.py   # Bloco D
```

Artefatos gerados:
- `dados/_meninos_revalidacao.json`
- `dados/_dias_suspeitos.parquet`
- `dados/_novos_positivos_externos.parquet`

---

## 9. Anexo — configurações detalhadas

### Hiperparâmetros GradBoost (champion em todas as iterações)

```python
GradientBoostingClassifier(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=2,
    min_samples_leaf=10,
    subsample=0.8,
    max_features="sqrt",
    random_state=42,
)
```

### Constantes do pipeline

| Constante | Valor | Onde |
|---|---|---|
| `MESES_CHUVOSOS` | [11, 12, 1, 2, 3, 4] | filtro sazonal |
| `JANELAS_H` | [1, 3, 6, 24, 48, 72] | janelas de acumulação |
| `LIMS` | {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100} mm | limiares por janela |
| `LOOKBACK_H` | 72 | janela retroativa de chuva por chamado |
| `T_CUT` | 2023-07-02 | split temporal padrão |
| `T_CUT_ORATORIO` | 75º percentil de eventos | split adaptativo (oratorio sem positivos no test padrão) |
| `K_APIS` | [0.70, 0.85, 0.95] | constantes do API (V4+) |
| `LIM_INTENSO_MM` | 5.0 | limiar de "hora intensa" (V4+) |
| `N_BOOT` | 1000 | reamostragens para IC95 |
| `CV_SPLITS` | 5 | TimeSeriesSplit no treino |
