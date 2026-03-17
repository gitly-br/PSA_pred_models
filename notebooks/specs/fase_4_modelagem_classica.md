# Fase 4: Modelagem Clássica (Baseline)

## Objetivo

Treinar e avaliar modelos clássicos de ML por bacia. Responde: **"Qual modelo melhor prediz enchentes por bacia usando features de chuva CEMADEN?"**

## Inputs

| Arquivo | Descrição | Origem |
|---------|-----------|--------|
| `dados/features_24h.parquet` | Features de janela 24h | Fase 3 |
| `dados/features_48h.parquet` | Features de janela 48h | Fase 3 |
| `dados/target_por_bacia.parquet` | Target binário por (data, bacia) | Fase 3 |
| `dados/percentis_chuva.json` | Thresholds de percentil por bacia | Fase 2 |

## Outputs

| Artefato | Descrição |
|----------|-----------|
| `modelos/baseline_<bacia>.pkl` | Melhor modelo por bacia |
| `modelos/metricas_baseline.json` | Métricas por bacia por modelo |
| `dados/predictions_baseline.parquet` | Predições no test set com probabilidades |

## Células planejadas

1. **Carga + split temporal** — train 2016-2022, test 2023-2024
2. **Baseline: dummy classifier** — mostrar que accuracy ~90% é enganosa
3. **Resampling** — undersampling por cluster (KMeans nos negativos) + SMOTE para comparação
4. **Model zoo (scikit-learn)** — Logistic Regression, LDA/QDA, Naive Bayes, Decision Tree, Random Forest, Extra Trees, Gradient Boosting, XGBoost, LightGBM
5. **Tabela de métricas** — Accuracy, AUC, Recall, Precision, F1, MCC — ordenar por F1
6. **Avaliação condicionada a percentil** — avaliar só em dias com chuva >p75/p90/p95. Mostrar melhoria de precision
7. **Matrizes de confusão** — plotly para top 3 modelos por bacia
8. **Feature importance** — tree-based, comparar entre bacias
9. **Seleção de campeão por bacia** — melhor F1 sob condição p75
10. **Learning curves**
11. **Export** — modelos (joblib) + métricas JSON + predições parquet

## Lições dos notebooks antigos (Modelos_SA.ipynb, Modelos_V1.ipynb)

- **Split temporal** — train 2016-2022, test 2023-2024 (não random)
- **Filtro sazonal** — remover meses 5-10 (seca), confirmado em ambos notebooks
- **Undersampling por cluster** — KMeans nos negativos, sample de cada cluster
- **Avaliação condicionada a percentil** — precision melhora dramaticamente em dias com chuva >p75
- **Modelagem por bacia** — cada bacia tem dinâmica diferente
- **Recall > Precision** — para desastres, perder enchente é pior que falso alarme (mas target Precision >50%)
- **Melhores features (histórico):** visibilidade média 12-18h, ponto de orvalho 6-12h, delta visibilidade, sensação térmica, delta precipitação

## Decisões tomadas

_(nenhuma ainda)_

## Decisões pendentes

- Adicionar xgboost e lightgbm ao `pyproject.toml`?
- Usar scikit-learn direto (recomendado) vs pycaret (notebooks antigos)?
- Ratio de undersampling: testar 1:0.75, 1:1, 1:0.5
- CV: time-series split (expanding window) vs blocked K-fold?
- Um modelo por bacia ou multi-bacia com bacia como feature?

## Dependências

Fase 3 completa.
