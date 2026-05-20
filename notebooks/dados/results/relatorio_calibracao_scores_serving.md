# Relatório: Calibração de Scores para Serving

**Data:** 2026-05-20 11:10  
**Script:** `_calibracao_scores_serving.py`  
**Calibrador recomendado:** `piecewise`  
**Candidato primário:** `combinador_mean`

---

## 1. Objetivo

Transformar score bruto do combinador em percentual operacional interpretável
para dashboard, preservando a proporcionalidade com a intensidade da chuva.

## 2. Calibrações Testadas

| Calibrador | Descrição | Leak? |
|------------|-----------|-------|
| platt | Regressão logística (Platt scaling) sobre treino | Não |
| isotonic | Regressão isotônica sobre treino | Não |
| quantile | Mapeamento para percentil empírico do treino | Não |
| piecewise | Linear por bins do score bruto (5 bins) | Não |
| piecewise_operacional | Piecewise com targets 0.30 e 0.70 nos P30/P70 do treino | Não |

> **Nota:** Calibração por faixas de chuva ou severidade foi avaliada como
> inviável *sem leak*, pois ambas dependem de informação futura/observada
> no dia D. O piecewise usa apenas o próprio score bruto para definir bins.

## 3. Métricas Agregadas (média entre bacias)

| Calibrador | Brier ↓ | PR-AUC | Spearman max_dia | Spearman severidade |
|------------|---------|--------|------------------|---------------------|
| piecewise    | 0.1034 | 0.1987 | 0.183 | 0.111 |
| quantile     | 0.1051 | 0.1998 | 0.181 | 0.102 |
| isotonic     | 0.0596 | 0.1170 | 0.153 | 0.155 |
| platt        | 0.0576 | 0.1998 | 0.181 | 0.102 |
| piecewise_operacional | 0.1029 | 0.1998 | 0.181 | 0.102 |

## 4. Comparação Antes vs Depois (combinador_mean)

| Métrica | Bruto | Platt | Isotonic | Quantile | Piecewise | Pw-Operacional |
|---------|-------|-------|----------|----------|-----------|---------------|
| Brier          | 0.0600 | 0.0575 | 0.0583 | 0.1287 | 0.1271 | 0.1287 | 
| PR-AUC         | 0.1973 | 0.1973 | 0.1412 | 0.1973 | 0.1957 | 0.1973 | 
| Spearman max_dia | 0.158 | 0.158 | 0.190 | 0.158 | 0.163 | 0.158 | 
| Spearman severid | 0.095 | 0.095 | 0.203 | 0.095 | 0.102 | 0.095 | 

## 5. Curva Score por Faixa de Chuva (combinador_mean + recomendado)

| Bacia | Faixa | n | Score Bruto Médio | Score Calibrado Médio | Severidade Média |
|-------|-------|---|-------------------|-----------------------|------------------|
| tamanduatei | 0-5     | 183 | 0.138 | 0.252 | 0.03 |
| tamanduatei | 5-10    | 30  | 0.166 | 0.335 | 0.10 |
| tamanduatei | 10-20   | 27  | 0.170 | 0.336 | 0.78 |
| tamanduatei | 20-30   | 2   | 0.082 | 0.088 | 2.00 |
| meninos | 0-5     | 194 | 0.088 | 0.258 | 0.02 |
| meninos | 5-10    | 25  | 0.108 | 0.349 | 0.00 |
| meninos | 10-20   | 21  | 0.097 | 0.305 | 0.14 |
| meninos | 20-30   | 2   | 0.107 | 0.338 | 1.50 |
| guarara | 0-5     | 187 | 0.123 | 0.243 | 0.03 |
| guarara | 5-10    | 31  | 0.152 | 0.355 | 0.10 |
| guarara | 10-20   | 22  | 0.143 | 0.301 | 1.00 |
| guarara | 20-30   | 2   | 0.082 | 0.126 | 2.00 |
| oratorio | 0-5     | 196 | 0.120 | 0.239 | 0.00 |
| oratorio | 5-10    | 30  | 0.137 | 0.284 | 0.00 |
| oratorio | 10-20   | 15  | 0.142 | 0.340 | 0.27 |
| oratorio | 20-30   | 1   | 0.093 | 0.124 | 1.00 |
| global  | 0-5     | 760 | 0.117 | 0.256 | 0.02 |
| global  | 5-10    | 116 | 0.142 | 0.342 | 0.05 |
| global  | 10-20   | 85  | 0.140 | 0.331 | 0.59 |
| global  | 20-30   | 7   | 0.090 | 0.175 | 1.71 |

## 6. Critérios Operacionais

Distribuição do score calibrado recomendado por intensidade de chuva no teste:
- **Leve (<30%)**: esperado para chuvas leves (<10mm)
- **Moderada (30-70%)**: para chuvas moderadas (10-20mm) com perfil perigoso
- **Forte (>70%)**: para chuvas fortes (>=20mm)

- **tamanduatei — geral** (n=242): leve 62.0%, moderada 35.1%, forte 2.9%
- **tamanduatei — leve_chuva** (n=213): leve 63.4%, moderada 33.8%, forte 2.8%
- **tamanduatei — moderada_chuva** (n=27): leve 48.1%, moderada 48.1%, forte 3.7%
- **tamanduatei — forte_chuva** (n=2): leve 100.0%, moderada 0.0%, forte 0.0%
- **tamanduatei — evento** (n=23): leve 47.8%, moderada 47.8%, forte 4.3%
- **meninos — geral** (n=242): leve 63.2%, moderada 33.5%, forte 3.3%
- **meninos — leve_chuva** (n=219): leve 63.9%, moderada 32.9%, forte 3.2%
- **meninos — moderada_chuva** (n=21): leve 57.1%, moderada 38.1%, forte 4.8%
- **meninos — forte_chuva** (n=2): leve 50.0%, moderada 50.0%, forte 0.0%
- **meninos — evento** (n=7): leve 28.6%, moderada 28.6%, forte 42.9%
- **guarara — geral** (n=242): leve 61.6%, moderada 34.7%, forte 3.7%
- **guarara — leve_chuva** (n=218): leve 62.4%, moderada 35.3%, forte 2.3%
- **guarara — moderada_chuva** (n=22): leve 50.0%, moderada 31.8%, forte 18.2%
- **guarara — forte_chuva** (n=2): leve 100.0%, moderada 0.0%, forte 0.0%
- **guarara — evento** (n=25): leve 48.0%, moderada 32.0%, forte 20.0%
- **oratorio — geral** (n=242): leve 65.3%, moderada 31.8%, forte 2.9%
- **oratorio — leve_chuva** (n=226): leve 66.8%, moderada 30.5%, forte 2.7%
- **oratorio — moderada_chuva** (n=15): leve 40.0%, moderada 53.3%, forte 6.7%
- **oratorio — forte_chuva** (n=1): leve 100.0%, moderada 0.0%, forte 0.0%
- **oratorio — evento** (n=5): leve 40.0%, moderada 60.0%, forte 0.0%
- **global — geral** (n=968): leve 62.1%, moderada 33.1%, forte 4.9%
- **global — leve_chuva** (n=876): leve 62.9%, moderada 33.1%, forte 4.0%
- **global — moderada_chuva** (n=85): leve 51.8%, moderada 34.1%, forte 14.1%
- **global — forte_chuva** (n=7): leve 85.7%, moderada 14.3%, forte 0.0%
- **global — evento** (n=60): leve 40.0%, moderada 36.7%, forte 23.3%

## 7. Recomendação

O calibrador **`piecewise`** foi selecionado pelo critério composto:
- Preservar Spearman com `max_dia` (proporcionalidade)
- Minimizar Brier score (probabilidade bem calibrada)
- Manter PR-AUC razoável

## 8. Uso para Dashboard

O score calibrado está no intervalo **[0, 1]** (0-100%).
Para exibição no dashboard:
- `0-30%` → **Baixo**
- `30-70%` → **Moderado**
- `70-100%` → **Alto**

A coluna gerada no parquet é: `risk_score_raw_mean_serving`.

## 9. Limitações Conhecidas

- O calibrador foi ajustado em dados históricos até 2024-07-01; drift temporal pode degradar performance.
- Poucos eventos extremos (>30mm) no teste; calibração na cauda tem alta variância.
- Calibração por faixas de chuva/severidade foi evitada para prevenir leak; o piecewise usa bins do score bruto.
- **Limitação crítica do score bruto**: o combinador_mean raramente produz valores >0.60 (máx 0.5986 no dataset), o que impede que qualquer calibração monotônica atinja >70% para eventos fortes de forma consistente. Isso indica que o combinador subestima o risco de eventos extremos e/ou o score não está suficientemente correlacionado com chuva volumétrica.
- O score calibrado é usável para ranking relativo (comparar dias), mas os thresholds operacionais absolutos (30%/70%) devem ser interpretados com cautela até que o score bruto tenha maior resolução na cauda.

## 10. Arquivos Gerados

- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/calibracao_scores_serving.parquet` — scores calibrados por dia/bacia
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/calibracao_scores_serving_metricas.parquet` — métricas comparativas
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/calibracao_scores_serving_faixas.parquet` — curva score por faixa de chuva
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/calibracao_scores_serving_criterios.parquet` — critérios operacionais
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/calibracao_scores_serving_params.json` — parâmetros do calibrador recomendado
- `/home/rnicola/Documents/Projects/PSA/notebooks/dados/results/relatorio_calibracao_scores_serving.md` — este relatório
