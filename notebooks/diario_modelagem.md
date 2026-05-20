# Diário de Desenvolvimento de Modelos — PSA Flood Prediction

**Data:** 2026-05-20  
**Sessão:** Benchmark V8 + Experimentos Paralelos (Calibração, Regressão, Features, Monotônico, OpenMeteo)
**Modelo:** kimi-k2.6  
**Status:** Em andamento — diagnóstico realizado, próxima rodada de experimentos em paralelo

---

## 1. Contexto

O objetivo é melhorar o modelo de predição de severidade de enchentes (0–3) por bacia hidrográfica. O usuário não busca necessariamente alta precisão/recall no target categórico; o que ele quer é **probabilidade proporcional à intensidade da chuva**: dias com muita chuva → prob alta; dias com pouca chuva → prob próxima de zero.

---

## 2. Estado Inicial (Benchmark V7)

- Modelo: `ChampionOrdinalModel` com 3 `GradientBoostingClassifier` binários em cascata (m1: ≥1, m2: ≥2, m3: ≥3)
- Features: 27 features derivadas do CEMADEN (APIs, lags 6h, lags diários, acumulados, cíclicos)
- Thresholds: otimizados por F1 via TimeSeriesSplit
- Problema identificado: **leak do target** — o `_run_modelos_v7.py` usava `max_dia[t]` (dia atual) nas APIs, enquanto `export_champion.py` já tinha corrigido com `shift(1)`

---

## 3. Benchmark V8 — Leak Corrigido + Holdout Dedicado

### Script
`/notebooks/scripts/experiments/_run_benchmark_v8.py`

### Metodologia
- Feature engineering com **leak corrigido**: `api_*` usa `shift(1)` em `max_dia` antes do `lfilter`
- Holdout: 75% treino → 25% val_holdout (tuning de threshold) → test set (dados nunca vistos)
- Modelos testados: GradBoost e LGBM

### Resultados (Test Set)

| Bacia | Modelo | k | PRAUC | Recall | Prec | F1 | Spearman ρ |
|-------|--------|---|-------|--------|------|----|------------|
| Guarara | GradBoost | 1 | 0.189 | 0.553 | 0.158 | 0.246 | 0.217 |
| Meninos | GradBoost | 1 | 0.093 | 1.000 | 0.024 | 0.046 | 0.207 |
| Oratorio | GradBoost | 1 | 0.114 | 1.000 | 0.045 | 0.086 | 0.195 |
| Tamanduatei | GradBoost | 1 | 0.141 | 0.432 | 0.200 | 0.274 | 0.224 |

**Spearman ρ médio: 0.211**

---

## 4. Experimento 1 — Calibração de Probabilidade (IsotonicRegression)

### Script
`/notebooks/scripts/experiments/_calibracao_probabilidade.py`

### Hipótese
O modelo aprende a ordenação mas a probabilidade está mal calibrada. IsotonicRegression deveria melhorar a escala das probabilidades.

### Resultado
**Não ajudou.** A isotônica é monotônica crescente, logo preserva a ordenação. Como o threshold F1 depende apenas da ordenação, Prec/Recall/F1 ficaram **exatamente iguais** ao baseline. PRAUC até caiu levemente em alguns casos.

**Spearman ρ:** sem mudança relevante.

---

## 5. Experimento 2 — Regressão Direta em Severidade

### Script
`/notebooks/scripts/experiments/_regressao_severidade.py`

### Hipótese
Em vez de 3 classificadores binários, treinar 1 regressor para prever severidade 0-3 como valor contínuo. A probabilidade de evento seria derivada do output.

### Resultado
- **Estratégia linear** (`output / 2`): Precisão subiu 2.5-4x (7-10% → 13-27%), mas **recall caiu para 10-19%**
- **Estratégia sigmoid**: Recall recuperado (42-68%), precisão volta para ~12-15%
- **PRAUC piorou** vs baseline (0.175 vs 0.256 no melhor caso)
- Spearman ρ: 0.11-0.24 (similar ao baseline)

**Conclusão:** regressão pura não superou baseline em capacidade discriminativa, mas ofereceu curva de precisão-recall mais útil.

---

## 6. Experimento 3 — Feature Engineering V2 (Agressivo)

### Script
`/notebooks/scripts/experiments/_feature_engineering_v2.py`

### Hipótese
Features adicionais (tendência, saturação, pico relativo, acumulados 24h/48h, interações) deveriam capturar melhor a magnitude do risco.

### Resultado
- Spearman ρ: **0.211 → 0.227** (+0.016) — melhorou levemente
- PRAUC k=1: quase estável (0.135 → 0.139 média)
- **Problema crítico no gráfico:** prob média = 0 para chuvas >30mm no test set

**Conclusão:** features novas ajudaram marginalmente na ordenação, mas não resolveram a subestimação de eventos extremos.

---

## 7. Experimento 4 — OpenMeteo como Features

### Script
`/notebooks/scripts/experiments/_openmeteo_features.py`

### Hipótese
Dados de temperatura, umidade, pressão e vento do OpenMeteo poderiam ajudar a discriminar dias com mesma chuva mas comportamento diferente.

### Resultado
- Spearman ρ: leve aumento (+0.006 a +0.034 por bacia)
- **PRAUC caiu** na maioria dos casos (ex: Guarara k=1: 0.189 → 0.157)
- Recall subiu em alguns casos, mas ao custo de queda de precisão → F1 menor ou igual

**Conclusão:** OpenMeteo não trouxe ganho discriminativo. As variáveis parecem correlacionadas com sazonalidade (já capturada por `mes_sin`/`mes_cos`) e introduziram ruído.

---

## 8. Experimento 5 — XGBoost com Constraints Monotônicas

### Script
`/notebooks/scripts/experiments/_xgboost_monotonico.py`

### Hipótese
Forçar relação monotônica positiva entre features de chuva e probabilidade deveria garantir comportamento proporcional.

### Resultado
- **PRAUC k=1:** monotônico venceu (0.123 vs 0.098) — melhor discriminação
- **Spearman ρ:** monotônico **PERDEU** (0.180 vs 0.223) — pior correlação com chuva!
- Constraints muito rígidas podem estar impedindo o modelo de aprender interações úteis

**Conclusão:** constraints monotônicas melhoraram PRAUC mas pioraram a proporcionalidade que o usuário quer.

---

## 9. Experimento 6 — Análise de Probabilidade por Faixa de Chuva

### Script
`/notebooks/scripts/experiments/_analise_prob_chuva.py`

### Objetivo
Entender se o modelo atual já mostra comportamento proporcional razoável.

### Resultado (Test Set)

| Faixa (mm) | Taxa Real Positivos | Prob Predita (Média) | Diferença |
|------------|---------------------|----------------------|-----------|
| 0-5 | 0.2-1.2% | 6-14% | **+5-13%** (superestima) |
| 5-10 | 0-3.4% | 8-16% | **+5-15%** (superestima) |
| 10-20 | 17-84% | 10-18% | **-66%** (subestima) |
| 20-30 | **100%** | **9-15%** | **-85%** (subestima MUITO) |

**Em Guarara, a probabilidade predita DESCE quando a chuva aumenta:** 5-10mm → 15.9%, 20-30mm → 10.7%.

**Spearman ρ médio: 0.258**

### Diagnóstico
O modelo é **muito conservador**. Aprendeu a dizer "não" para quase tudo devido ao desbalanceamento extremo (88-95% negativos). Quando vê chuva de 20-30mm (100% positivo na realidade), atribui apenas 9-15% de probabilidade.

---

## 10. Diagnóstico Consolidado

### O que não funciona:
- Calibração isotônica (preserva ordenação, não muda decisões)
- OpenMeteo como features (ruído > sinal)
- Constraints monotônicas rígidas (melhoram PRAUC, pioram Spearman)
- Regressão pura (melhora precisão, perde recall, PRAUC piora)

### O que funciona parcialmente:
- Feature engineering V2 (+0.016 em Spearman, mas ainda insuficiente)

### Problema raiz:
O modelo **não consegue aprender a magnitude do risco** porque:
1. Desbalanceamento extremo (5-12% positivos)
2. `max_depth=2` é muito restritivo
3. Threshold otimizado por F1, não por proporcionalidade com chuva

---

## 11. Próximos Passos Planejados

### A. Modelo de Cauda Pesada
- `max_depth` maior (4-6)
- Sample weights agressivos: sev 0→0.1, 1→1.0, 2→5.0, 3→20.0
- Threshold fixo baixo (0.1) — deixar probabilidade "respirar"
- Avaliar por Spearman ρ, não F1
- Plotar curva prob vs chuva

### B. Análise de Perfis de Chuva (Forecast → Regressão Temporal)
- Usar dados de forecast do OpenMeteo
- Identificar dois perfis preocupantes:
  1. **Pancada pontual**: pico alto, curta duração
  2. **Chuva prolongada**: acumulado alto, longa duração
- Treinar regressão da série temporal de forecast para prever se próxima janela terá evento de perfil preocupante

### C. Modelos Especialistas (Pancada vs Prolongada)
- Modelo especialista em **pancadas de chuva** (foco em picos, max_dia, pico_1h, horas_intensas)
- Modelo especialista em **chuva prolongada** (foco em acumulados, APIs, acum_7d/30d)
- Preditor final: ensemble dos dois especialistas

---

## Arquivos Gerados Nesta Sessão

- `notebooks/scripts/experiments/_run_benchmark_v8.py`
- `notebooks/scripts/experiments/_calibracao_probabilidade.py`
- `notebooks/scripts/experiments/_regressao_severidade.py`
- `notebooks/scripts/experiments/_feature_engineering_v2.py`
- `notebooks/scripts/experiments/_openmeteo_features.py`
- `notebooks/scripts/experiments/_xgboost_monotonico.py`
- `notebooks/scripts/experiments/_analise_prob_chuva.py`
- `notebooks/dados/results/benchmark_v8_leak_corrected.parquet`
- `notebooks/dados/results/feature_engineering_v2.parquet`
- `notebooks/dados/results/openmeteo_features.parquet`
- `notebooks/dados/results/feature_engineering_v2_prob_por_faixa.png`
- `notebooks/dados/results/openmeteo_prob_por_faixa_chuva.png`
- `notebooks/dados/results/xgboost_prob_por_faixa_chuva.png`
- `notebooks/dados/results/analise_prob_chuva_barras.png`
- `notebooks/dados/results/analise_prob_chuva_scatter.png`
- `notebooks/dados/results/analise_prob_chuva_faixas.parquet`

---

## Notas para Próxima Sessão

- Verificar se há dados suficientes de chuva >30mm no treino (o modelo pode nunca ter visto esses exemplos)
- Considerar se a feature `max_dia` do próprio dia (com leak) poderia ser usada em alguma forma segura (ex: como target secundário)
- Avaliar se o problema é realmente de modelo ou de representação — talvez 27 features não sejam suficientes para capturar a física do escoamento

---

## 12. Correção de Direção — Forecast como Detector de Perfil Perigoso

Após revisar os resultados do experimento `perfis_chuva_forecast`, foi identificado que a avaliação feita pelo agente respondeu parcialmente à pergunta errada. O forecast OpenMeteo **não deve ser tratado como substituto do CEMADEN histórico**. A função correta do forecast é prever, antes do evento, se as próximas janelas horárias terão **perfil meteorológico perigoso**.

### Nova interpretação correta

- CEMADEN histórico continua sendo a melhor fonte para memória hidrológica/local do sistema.
- OpenMeteo/forecast deve atuar como preditor de **chuva futura perigosa**.
- O output desejado não é apenas `P(chamado >= 1)`, mas uma probabilidade operacional de:
  - pancada forte pontual;
  - chuva prolongada/saturante;
  - evento preocupante combinado.

### Falhas metodológicas observadas no experimento anterior

1. O agente comparou o forecast contra o benchmark CEMADEN como se fossem substitutos diretos.
2. Os thresholds de perfil foram definidos de forma simplificada e possivelmente incompatível com a escala do OpenMeteo.
3. A avaliação não separou claramente:
   - qualidade do forecast para prever chuva real;
   - qualidade do perfil perigoso para explicar chamados/alagamentos.
4. O resultado `PRAUC baixo` para forecast sozinho não invalida a abordagem, pois ela é arquiteturalmente complementar.

### Nova rodada planejada

Serão lançados agentes paralelos com contratos mais específicos:

1. **Auditoria temporal dos dados de forecast**: confirmar se os parquets representam forecast emitido antes do evento ou reanálise/histórico.
2. **Detector de perfis perigosos via forecast**: prever pancada/prolongada como evento meteorológico futuro, avaliado contra CEMADEN futuro.
3. **Bias correction/downscaling forecast→CEMADEN**: calibrar OpenMeteo para escala CEMADEN por bacia antes de aplicar regras de perfil.
4. **Modelos especialistas pancada/prolongada**: relançar experimento anterior, pois o agente retornou sem relatório.

Critério de aceite desta rodada: cada agente deve retornar evidência objetiva. Se o contrato não for cumprido, o agente deve ser relançado com correção.
