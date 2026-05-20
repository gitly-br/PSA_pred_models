# Relatório: Combinador de Risco Meteorológico

**Data:** 2026-05-20 10:45  
**Script:** `_combinador_risco_meteorologico.py`  
**Candidato recomendado:** `combinador_mean`

---

## 1. Objetivo

Combinar as melhores linhas experimentais em um score único proporcional à
intensidade da chuva / perfil perigoso futuro, servindo como candidato principal
para calibração e serving.

## 2. Componentes Combinados

| # | Componente | Descrição | Fonte |
|---|------------|-----------|-------|
| 1 | Similaridade perfis | KMeans(k=2) sobre vetor passado+future; score = max(1/(1+dist)) | `_similaridade_perfis_chuva.py` |
| 2 | Forecast detector H48 perigoso_any | LogisticRegression FC_ONLY para `perigoso_any_h48` | `_forecast_detector_perfil_perigoso.py` |
| 3 | Forecast detector H48 saturante | LogisticRegression FC_ONLY para `saturante` (acum_48h_fut) | `_forecast_detector_perfil_perigoso.py` |
| 4 | Especialista pancada | GradBoost features de pico/intensidade curta | `_especialistas_pancada_prolongada.py` |
| 5 | Especialista prolongada | GradBoost features de acumulado/saturação | `_especialistas_pancada_prolongada.py` |
| 6 | Classificador cauda pesada | GradBoost max_depth=6, sample weights agressivos | `_ranking_cauda_pesada.py` |

## 3. Combinações Testadas

- **combinador_mean**: média simples dos 6 scores normalizados
- **combinador_weighted**: média ponderada (pesos proporcionais a Spearman relatado nos experimentos: fc=0.430, sat=0.585, panc=0.225, prol=0.179, cauda=0.191, sim=0.077)
- **combinador_max**: máximo entre os 6 scores normalizados

Todos os scores individuais são normalizados para [0,1] usando min/max do **treino** por bacia, garantindo que a escala do teste não seja artificialmente inflada.

## 4. Métricas Agregadas (média entre bacias)

| Modelo | PR-AUC | Spearman max_dia | Spearman severidade | Recall@thr0.1 | Prec@thr0.1 |
|--------|--------|------------------|---------------------|---------------|-------------|
| baseline_v8            | 0.147 | 0.258 | 0.143 | 0.594 | 0.115 |
| classificador_cauda    | 0.117 | 0.182 | 0.081 | 0.562 | 0.084 |
| combinador_max         | 0.133 | 0.277 | 0.102 | 1.000 | 0.062 |
| combinador_mean        | 0.141 | 0.351 | 0.151 | 0.810 | 0.071 |
| combinador_weighted    | 0.140 | 0.329 | 0.145 | 0.653 | 0.109 |
| especialista_pancada   | 0.148 | 0.293 | 0.145 | 0.578 | 0.095 |
| especialista_prolongada | 0.148 | 0.211 | 0.102 | 0.532 | 0.107 |
| forecast_detector      | 0.125 | 0.201 | 0.081 | 0.444 | 0.090 |
| forecast_detector_saturacao | 0.123 | 0.197 | 0.082 | 0.406 | 0.126 |
| similaridade           | 0.080 | 0.077 | -0.058 | 0.987 | 0.061 |

## 5. Inversoes (score 20-30mm < score 10-20mm)

| Modelo | Inversoes |
|--------|-----------|
| baseline_v8_prob       | 2 |
| risk_score_raw_max     | 1 |
| risk_score_raw_mean    | 0 |
| risk_score_raw_weighted | 1 |

## 6. Candidato Recomendado

**`combinador_mean`** foi selecionado pelo critério de melhor Spearman com max_dia
(proporcionalidade), com penalidade leve para PR-AUC muito baixo.

## 7. Limitações Conhecidas

- Forecast detector usa OpenWeather forecast history (1 ponto espacial), não captura
  variabilidade intra-bacia para eventos convectivos.
- Bias correction não foi aplicada operacionalmente nesta rodada por falta de
  pipeline automatizado; usamos forecast raw.
- Scores são normalizados usando estatísticas do treino por bacia, o que é mais
  robusto que normalizar no teste, mas ainda pode sofrer com drift temporal.
- Poucos eventos extremos (>30mm) no teste; estimativas na cauda têm alta variância.
- O componente de similaridade apresenta Spearman baixo (0.077) e correlação
  negativa com severidade; seu peso no combinador weighted é pequeno (0.077),
  mas ainda contribui para diversidade do ensemble.

## 8. Arquivos Gerados

- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/combinador_risco_meteorologico.parquet` — scores por dia/bacia (todas as variantes)
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/combinador_risco_meteorologico_metricas.parquet` — métricas por bacia/modelo
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/combinador_risco_meteorologico_faixas.parquet` — curva score médio por faixa de chuva
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/combinador_risco_meteorologico_inversoes.parquet` — diagnóstico de inversões
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/relatorio_combinador_risco_meteorologico.md` — este relatório
