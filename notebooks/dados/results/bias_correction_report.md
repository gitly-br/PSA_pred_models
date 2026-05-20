# Relatório: Bias Correction OpenMeteo → CEMADEN

**Data:** 2026-05-20 04:29

## Objetivo

Testar correções simples e auditáveis de viés entre OpenMeteo (ERA5-Land multipoint) e CEMADEN observado por bacia e horizonte, visando melhorar a detecção de perfis de chuva perigosos (pancada e prolongada).

## Dados

- **Fonte forecast:** ERA5-Land multipoint (OpenMeteo), 2016-2025
- **Fonte observada:** CEMADEN por bacia
- **Período de treino:** < 2023-07-02
- **Período de teste:** >= 2023-07-02
- **Meses analisados:** [11, 12, 1, 2, 3, 4]
- **Horizontes:** [12, 24, 48] horas

## Métodos testados

1. **Baseline:** sem correção (OpenMeteo raw)
2. **Multiplicador:** fator de escala ótimo (mediana da razão CEMADEN/OpenMeteo)
3. **Quantile Mapping:** mapeamento empírico de 100 quantis
4. **Regressão Linear:** OLS de CEMADEN ~ OpenMeteo
5. **Regressão Robusta (Theil-Sen):** regressão robusta a outliers

## Resultados por bacia/horizonte

### GUARARA

#### Horizonte H12h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 6.50 | 11.40 | 0.436 | 26.72 | 34.95 | 0.279 | 0.136 |
| multiplicador        | 9.69 | 16.37 | 0.436 | 24.77 | 26.39 | 0.279 | 0.136 |
| quantile_mapping     | 9.55 | 15.79 | 0.432 | 22.41 | 25.48 | 0.279 | 0.136 |
| regressao_linear     | 8.37 | 10.86 | 0.436 | 23.07 | 31.34 | 0.279 | 0.136 |
| regressao_robusta    | 6.63 | 11.23 | 0.436 | 25.46 | 33.29 | 0.279 | 0.136 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.172 | 0.104 | 0.261 | 0.857 | 0.273 | 0.250 |
| multiplicador        | 0.483 | 0.116 | 0.783 | 0.900 | 0.636 | 0.231 |
| quantile_mapping     | 0.483 | 0.119 | 0.783 | 0.900 | 0.636 | 0.237 |
| regressao_linear     | 0.414 | 0.140 | 0.217 | 0.833 | 0.545 | 0.279 |
| regressao_robusta    | 0.241 | 0.115 | 0.304 | 0.875 | 0.364 | 0.262 |

#### Horizonte H24h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 7.08 | 11.84 | 0.429 | 25.60 | 32.82 | 0.302 | 0.136 |
| multiplicador        | 8.90 | 14.50 | 0.430 | 24.64 | 29.13 | 0.302 | 0.136 |
| quantile_mapping     | 9.44 | 15.21 | 0.426 | 24.29 | 28.67 | 0.302 | 0.136 |
| regressao_linear     | 8.44 | 10.98 | 0.429 | 23.91 | 32.44 | 0.302 | 0.136 |
| regressao_robusta    | 6.64 | 11.33 | 0.430 | 26.43 | 34.77 | 0.302 | 0.136 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.241 | 0.099 | 0.391 | 0.900 | 0.364 | 0.225 |
| multiplicador        | 0.448 | 0.117 | 0.565 | 0.867 | 0.591 | 0.234 |
| quantile_mapping     | 0.448 | 0.112 | 0.609 | 0.875 | 0.591 | 0.224 |
| regressao_linear     | 0.241 | 0.095 | 0.174 | 1.000 | 0.364 | 0.216 |
| regressao_robusta    | 0.207 | 0.111 | 0.217 | 1.000 | 0.341 | 0.278 |

#### Horizonte H48h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 10.10 | 15.42 | 0.381 | 22.76 | 26.51 | 0.279 | 0.182 |
| multiplicador        | 8.16 | 12.67 | 0.381 | 23.49 | 29.77 | 0.279 | 0.182 |
| quantile_mapping     | 9.88 | 16.03 | 0.379 | 25.34 | 29.19 | 0.279 | 0.182 |
| regressao_linear     | 8.65 | 11.15 | 0.382 | 24.96 | 32.94 | 0.279 | 0.182 |
| regressao_robusta    | 6.78 | 11.44 | 0.381 | 27.68 | 35.92 | 0.279 | 0.182 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.483 | 0.097 | 0.565 | 0.929 | 0.591 | 0.179 |
| multiplicador        | 0.310 | 0.087 | 0.435 | 1.000 | 0.432 | 0.184 |
| quantile_mapping     | 0.310 | 0.080 | 0.522 | 0.923 | 0.455 | 0.179 |
| regressao_linear     | 0.138 | 0.057 | 0.087 | 1.000 | 0.273 | 0.171 |
| regressao_robusta    | 0.103 | 0.071 | 0.130 | 1.000 | 0.227 | 0.238 |

### MENINOS

#### Horizonte H12h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 5.95 | 10.22 | 0.446 | 23.30 | 26.85 | 0.302 | 0.318 |
| multiplicador        | 8.43 | 13.96 | 0.446 | 22.16 | 25.82 | 0.302 | 0.318 |
| quantile_mapping     | 8.14 | 13.11 | 0.442 | 18.73 | 19.92 | 0.302 | 0.318 |
| regressao_linear     | 7.41 | 9.75 | 0.446 | 20.82 | 25.32 | 0.302 | 0.318 |
| regressao_robusta    | 5.88 | 10.04 | 0.446 | 23.39 | 27.18 | 0.302 | 0.318 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.214 | 0.113 | 0.304 | 0.778 | 0.318 | 0.264 |
| multiplicador        | 0.429 | 0.107 | 0.696 | 0.842 | 0.568 | 0.223 |
| quantile_mapping     | 0.429 | 0.107 | 0.696 | 0.842 | 0.568 | 0.223 |
| regressao_linear     | 0.286 | 0.119 | 0.261 | 1.000 | 0.432 | 0.284 |
| regressao_robusta    | 0.143 | 0.082 | 0.304 | 0.875 | 0.273 | 0.245 |

#### Horizonte H24h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 6.51 | 10.72 | 0.440 | 21.76 | 24.95 | 0.302 | 0.318 |
| multiplicador        | 8.33 | 13.35 | 0.440 | 22.13 | 25.46 | 0.302 | 0.318 |
| quantile_mapping     | 8.11 | 12.78 | 0.433 | 19.98 | 21.36 | 0.302 | 0.318 |
| regressao_linear     | 7.54 | 9.86 | 0.440 | 21.90 | 26.82 | 0.302 | 0.318 |
| regressao_robusta    | 5.82 | 10.15 | 0.440 | 23.84 | 27.60 | 0.302 | 0.318 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.214 | 0.085 | 0.435 | 0.833 | 0.341 | 0.211 |
| multiplicador        | 0.393 | 0.100 | 0.565 | 0.812 | 0.523 | 0.209 |
| quantile_mapping     | 0.393 | 0.099 | 0.565 | 0.812 | 0.523 | 0.207 |
| regressao_linear     | 0.179 | 0.089 | 0.130 | 1.000 | 0.318 | 0.250 |
| regressao_robusta    | 0.143 | 0.093 | 0.261 | 1.000 | 0.250 | 0.256 |

#### Horizonte H48h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 9.61 | 14.55 | 0.395 | 18.41 | 20.03 | 0.302 | 0.318 |
| multiplicador        | 7.35 | 11.16 | 0.395 | 20.21 | 22.19 | 0.302 | 0.318 |
| quantile_mapping     | 8.25 | 13.08 | 0.391 | 19.14 | 19.62 | 0.302 | 0.318 |
| regressao_linear     | 7.70 | 9.99 | 0.395 | 22.83 | 28.04 | 0.302 | 0.318 |
| regressao_robusta    | 5.93 | 10.26 | 0.395 | 25.67 | 29.89 | 0.302 | 0.318 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.500 | 0.094 | 0.609 | 0.824 | 0.591 | 0.174 |
| multiplicador        | 0.250 | 0.067 | 0.435 | 1.000 | 0.364 | 0.152 |
| quantile_mapping     | 0.286 | 0.074 | 0.522 | 0.800 | 0.386 | 0.157 |
| regressao_linear     | 0.143 | 0.108 | 0.043 | 1.000 | 0.227 | 0.270 |
| regressao_robusta    | 0.143 | 0.154 | 0.087 | 1.000 | 0.182 | 0.308 |

### ORATORIO

#### Horizonte H12h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 5.71 | 10.00 | 0.423 | 22.85 | 27.63 | 0.273 | 0.273 |
| multiplicador        | 9.07 | 15.36 | 0.423 | 22.98 | 24.73 | 0.273 | 0.273 |
| quantile_mapping     | 8.26 | 13.98 | 0.422 | 22.61 | 24.54 | 0.273 | 0.273 |
| regressao_linear     | 7.08 | 9.46 | 0.424 | 20.09 | 26.08 | 0.273 | 0.273 |
| regressao_robusta    | 5.56 | 9.79 | 0.423 | 22.98 | 28.19 | 0.273 | 0.273 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.143 | 0.080 | 0.400 | 0.750 | 0.237 | 0.180 |
| multiplicador        | 0.393 | 0.098 | 0.733 | 0.733 | 0.500 | 0.170 |
| quantile_mapping     | 0.357 | 0.098 | 0.733 | 0.733 | 0.447 | 0.167 |
| regressao_linear     | 0.286 | 0.114 | 0.267 | 0.800 | 0.395 | 0.214 |
| regressao_robusta    | 0.143 | 0.091 | 0.333 | 0.833 | 0.237 | 0.205 |

#### Horizonte H24h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 6.24 | 10.67 | 0.428 | 21.22 | 25.88 | 0.318 | 0.227 |
| multiplicador        | 8.03 | 13.44 | 0.428 | 21.47 | 24.36 | 0.318 | 0.227 |
| quantile_mapping     | 7.97 | 13.72 | 0.430 | 21.80 | 24.35 | 0.318 | 0.227 |
| regressao_linear     | 7.17 | 9.54 | 0.428 | 20.86 | 27.40 | 0.318 | 0.227 |
| regressao_robusta    | 5.52 | 9.92 | 0.428 | 23.63 | 29.65 | 0.318 | 0.227 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.250 | 0.101 | 0.533 | 0.800 | 0.342 | 0.188 |
| multiplicador        | 0.321 | 0.087 | 0.667 | 0.769 | 0.447 | 0.165 |
| quantile_mapping     | 0.321 | 0.092 | 0.667 | 0.769 | 0.447 | 0.173 |
| regressao_linear     | 0.179 | 0.096 | 0.200 | 0.750 | 0.289 | 0.212 |
| regressao_robusta    | 0.143 | 0.105 | 0.200 | 0.750 | 0.237 | 0.237 |

#### Horizonte H48h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 9.33 | 14.80 | 0.389 | 18.83 | 20.91 | 0.318 | 0.182 |
| multiplicador        | 6.92 | 11.03 | 0.389 | 19.95 | 24.44 | 0.318 | 0.182 |
| quantile_mapping     | 8.37 | 15.50 | 0.390 | 22.38 | 25.71 | 0.318 | 0.182 |
| regressao_linear     | 7.29 | 9.62 | 0.389 | 21.28 | 28.02 | 0.318 | 0.182 |
| regressao_robusta    | 5.67 | 9.96 | 0.389 | 24.43 | 31.03 | 0.318 | 0.182 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.393 | 0.079 | 0.733 | 0.786 | 0.500 | 0.136 |
| multiplicador        | 0.250 | 0.074 | 0.467 | 0.875 | 0.368 | 0.149 |
| quantile_mapping     | 0.250 | 0.069 | 0.600 | 0.818 | 0.368 | 0.139 |
| regressao_linear     | 0.143 | 0.093 | 0.133 | 0.667 | 0.263 | 0.233 |
| regressao_robusta    | 0.107 | 0.115 | 0.133 | 0.667 | 0.158 | 0.231 |

### TAMANDUATEI

#### Horizonte H12h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 7.04 | 12.33 | 0.437 | 29.15 | 35.20 | 0.279 | 0.227 |
| multiplicador        | 10.95 | 18.52 | 0.437 | 27.10 | 30.06 | 0.279 | 0.227 |
| quantile_mapping     | 9.89 | 16.06 | 0.437 | 24.74 | 28.20 | 0.279 | 0.227 |
| regressao_linear     | 8.83 | 11.57 | 0.437 | 24.70 | 31.23 | 0.279 | 0.227 |
| regressao_robusta    | 7.18 | 12.03 | 0.437 | 26.77 | 32.32 | 0.279 | 0.227 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.121 | 0.095 | 0.200 | 0.833 | 0.200 | 0.238 |
| multiplicador        | 0.424 | 0.111 | 0.680 | 0.810 | 0.560 | 0.222 |
| quantile_mapping     | 0.424 | 0.125 | 0.680 | 0.810 | 0.560 | 0.250 |
| regressao_linear     | 0.364 | 0.133 | 0.200 | 0.833 | 0.500 | 0.278 |
| regressao_robusta    | 0.333 | 0.157 | 0.280 | 0.875 | 0.440 | 0.314 |

#### Horizonte H24h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 7.49 | 12.58 | 0.423 | 27.82 | 34.00 | 0.326 | 0.227 |
| multiplicador        | 9.80 | 15.94 | 0.423 | 26.74 | 32.53 | 0.326 | 0.227 |
| quantile_mapping     | 9.78 | 15.60 | 0.424 | 25.62 | 30.80 | 0.326 | 0.227 |
| regressao_linear     | 9.00 | 11.74 | 0.424 | 26.05 | 32.70 | 0.326 | 0.227 |
| regressao_robusta    | 7.25 | 12.18 | 0.423 | 27.91 | 34.10 | 0.326 | 0.227 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.182 | 0.091 | 0.240 | 0.857 | 0.300 | 0.227 |
| multiplicador        | 0.394 | 0.116 | 0.520 | 0.867 | 0.520 | 0.232 |
| quantile_mapping     | 0.394 | 0.116 | 0.520 | 0.867 | 0.520 | 0.232 |
| regressao_linear     | 0.303 | 0.125 | 0.120 | 1.000 | 0.400 | 0.250 |
| regressao_robusta    | 0.182 | 0.098 | 0.200 | 1.000 | 0.300 | 0.246 |

#### Horizonte H48h

| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |
|--------|-----|------|------------|---------|---------|---------|---------|
| baseline             | 10.14 | 15.53 | 0.383 | 24.74 | 30.62 | 0.279 | 0.273 |
| multiplicador        | 8.72 | 13.50 | 0.383 | 25.71 | 31.07 | 0.279 | 0.273 |
| quantile_mapping     | 10.32 | 16.85 | 0.386 | 27.68 | 34.41 | 0.279 | 0.273 |
| regressao_linear     | 9.19 | 11.90 | 0.382 | 27.12 | 33.72 | 0.279 | 0.273 |
| regressao_robusta    | 7.41 | 12.22 | 0.383 | 29.53 | 35.58 | 0.279 | 0.273 |

**Classificação de perfis:**

| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |
|--------|----------|-----------|----------|-----------|----------|-----------|
| baseline             | 0.515 | 0.120 | 0.480 | 0.923 | 0.580 | 0.204 |
| multiplicador        | 0.273 | 0.087 | 0.440 | 1.000 | 0.400 | 0.192 |
| quantile_mapping     | 0.303 | 0.091 | 0.480 | 0.923 | 0.420 | 0.191 |
| regressao_linear     | 0.242 | 0.096 | 0.080 | 1.000 | 0.340 | 0.205 |
| regressao_robusta    | 0.121 | 0.077 | 0.120 | 1.000 | 0.220 | 0.212 |

## Método vencedor por bacia/horizonte

Critério: maximizar `score = -MAE + 50 * recall_combinado` (equilibra erro global e capacidade de detectar eventos perigosos).

| Bacia | Horizonte | Método | MAE | RMSE | Spearman ρ | Recall Comb | F1 Comb |
|-------|-----------|--------|-----|------|------------|-------------|---------|
| guarara     | H12h | quantile_mapping     | 9.55 | 15.79 | 0.432 | 0.636 | 0.346 |
| guarara     | H24h | multiplicador        | 8.90 | 14.50 | 0.430 | 0.591 | 0.335 |
| guarara     | H48h | baseline             | 10.10 | 15.42 | 0.381 | 0.591 | 0.275 |
| meninos     | H12h | quantile_mapping     | 8.14 | 13.11 | 0.442 | 0.568 | 0.321 |
| meninos     | H24h | quantile_mapping     | 8.11 | 12.78 | 0.433 | 0.523 | 0.297 |
| meninos     | H48h | baseline             | 9.61 | 14.55 | 0.395 | 0.591 | 0.269 |
| oratorio    | H12h | multiplicador        | 9.07 | 15.36 | 0.423 | 0.500 | 0.253 |
| oratorio    | H24h | quantile_mapping     | 7.97 | 13.72 | 0.430 | 0.447 | 0.250 |
| oratorio    | H48h | baseline             | 9.33 | 14.80 | 0.389 | 0.500 | 0.213 |
| tamanduatei | H12h | quantile_mapping     | 9.89 | 16.06 | 0.437 | 0.560 | 0.346 |
| tamanduatei | H24h | quantile_mapping     | 9.78 | 15.60 | 0.424 | 0.520 | 0.321 |
| tamanduatei | H48h | baseline             | 10.14 | 15.53 | 0.383 | 0.580 | 0.302 |

## Limitações

- **Dados de forecast:** usamos ERA5-Land histórico (reanálise) como proxy de forecast perfeito. Em operação real, o forecast terá erro de emissão adicional.
- **Máximo diário:** OpenMeteo fornece precipitação horária média dos pontos da grade. Não captura picos pontuais de estações individuais do CEMADEN.
- **Correção univariada:** apenas precipitação é corrigida. Temperatura, umidade e pressão não foram incluídas neste experimento.
- **Perfis:** classificação de 'pancada' usa max_dia do CEMADEN como ground truth, mas o forecast corrigido ainda é proxy de acumulado, não de pico horário.

## Recomendação

O método mais frequente entre os vencedores foi **quantile_mapping** (6 de 12 combinações).
Para uso operacional, recomenda-se:
1. Calibrar o fator multiplicador por bacia/horizonte em janela rolante (ex: últimos 90 dias).
2. Validar com dados de forecast real (GFS/ICON) assim que disponíveis.
3. Considerar ensemble de multiplicador + quantile mapping para robustez.
4. Se o objetivo for apenas classificação de perfil, quantile mapping tende a preservar melhor a cauda.
