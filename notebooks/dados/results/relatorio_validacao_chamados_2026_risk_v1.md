# Validação Chamados 2026 — Risk Model V1 Robust

- Modelo: `gradboost_cons`
- Variante: `CEMADEN_OM`
- Score principal recomendado: `prob_perigoso_any`
- Componentes: `prob_pancada`, `prob_prolongada`, `prob_saturante`
- 2026 é pontuado com treino até 2025; controles 2025 usam treino pré-T_CUT.

## Datas de chamados no arquivo

| data_ocorrencia | bacia | len |
| --- | --- | --- |
| 2026-01-04 |  | 1 |
| 2026-01-07 | guarara | 5 |
| 2026-01-15 | oratorio | 4 |
| 2026-01-16 | oratorio | 1 |
| 2026-02-24 | meninos | 1 |
| 2026-02-24 | oratorio | 3 |
| 2026-02-24 | tamanduatei | 2 |
| 2026-03-06 | guarara | 7 |
| 2026-03-07 |  | 1 |
| 2026-03-08 | oratorio | 1 |
| 2026-04-01 | meninos | 2 |
| 2026-04-01 | oratorio | 1 |
| 2026-04-01 | tamanduatei | 8 |
| 2026-07-01 | guarara | 1 |
| 2026-12-01 | oratorio | 1 |

## Probabilidades por bacia nos dias de chamado

| data | bacia | n_chamados_validacao | max_dia | prob_perigoso_any | prob_saturante | prob_prolongada | prob_pancada |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-01-04 | guarara | 0 | 13.340 | 0.695 | 0.765 | 0.610 | 0.372 |
| 2026-01-04 | meninos | 0 | 2.360 | 0.624 | 0.719 | 0.563 | 0.288 |
| 2026-01-04 | oratorio | 0 | 3.940 | 0.846 | 0.891 | 0.539 | 0.426 |
| 2026-01-04 | tamanduatei | 0 | 7.720 | 0.869 | 0.874 | 0.612 | 0.326 |
| 2026-01-07 | guarara | 5 | 16.080 | 0.420 | 0.065 | 0.353 | 0.353 |
| 2026-01-07 | meninos | 0 | 16.080 | 0.275 | 0.165 | 0.256 | 0.154 |
| 2026-01-07 | oratorio | 0 | 12.600 | 0.222 | 0.071 | 0.295 | 0.194 |
| 2026-01-07 | tamanduatei | 0 | 16.080 | 0.430 | 0.088 | 0.350 | 0.263 |
| 2026-01-15 | guarara | 0 | 15.550 | 0.476 | 0.211 | 0.491 | 0.217 |
| 2026-01-15 | meninos | 0 | 15.360 | 0.640 | 0.441 | 0.540 | 0.243 |
| 2026-01-15 | oratorio | 4 | 21.020 | 0.393 | 0.276 | 0.401 | 0.235 |
| 2026-01-15 | tamanduatei | 0 | 14.290 | 0.604 | 0.456 | 0.630 | 0.188 |
| 2026-01-16 | guarara | 0 | 13.220 | 0.975 | 0.988 | 0.610 | 0.111 |
| 2026-01-16 | meninos | 0 | 22.080 | 0.980 | 0.976 | 0.768 | 0.513 |
| 2026-01-16 | oratorio | 1 | 23.160 | 0.978 | 0.984 | 0.369 | 0.130 |
| 2026-01-16 | tamanduatei | 0 | 23.160 | 0.979 | 0.985 | 0.710 | 0.093 |
| 2026-02-24 | guarara | 0 | 15.560 | 0.485 | 0.301 | 0.431 | 0.131 |
| 2026-02-24 | meninos | 1 | 15.140 | 0.478 | 0.237 | 0.381 | 0.225 |
| 2026-02-24 | oratorio | 3 | 22.320 | 0.420 | 0.187 | 0.243 | 0.220 |
| 2026-02-24 | tamanduatei | 2 | 22.320 | 0.475 | 0.393 | 0.527 | 0.266 |
| 2026-03-06 | guarara | 7 | 19.130 | 0.182 | 0.098 | 0.178 | 0.117 |
| 2026-03-06 | meninos | 0 | 13.010 | 0.174 | 0.063 | 0.207 | 0.092 |
| 2026-03-06 | oratorio | 0 | 15.990 | 0.206 | 0.064 | 0.171 | 0.072 |
| 2026-03-06 | tamanduatei | 0 | 19.130 | 0.218 | 0.040 | 0.170 | 0.100 |
| 2026-03-07 | guarara | 0 | 33.630 | 0.932 | 0.959 | 0.628 | 0.228 |
| 2026-03-07 | meninos | 0 | 8.770 | 0.973 | 0.968 | 0.665 | 0.287 |
| 2026-03-07 | oratorio | 0 | 5.120 | 0.888 | 0.921 | 0.333 | 0.258 |
| 2026-03-07 | tamanduatei | 0 | 16.010 | 0.931 | 0.937 | 0.670 | 0.301 |
| 2026-03-08 | guarara | 0 | 2.170 | 0.972 | 0.989 | 0.562 | 0.429 |
| 2026-03-08 | meninos | 0 | 4.330 | 0.972 | 0.972 | 0.606 | 0.136 |
| 2026-03-08 | oratorio | 1 | 15.570 | 0.789 | 0.798 | 0.343 | 0.122 |
| 2026-03-08 | tamanduatei | 0 | 7.530 | 0.949 | 0.947 | 0.808 | 0.263 |
| 2026-04-01 | guarara | 0 | 23.170 | 0.236 | 0.291 | 0.198 | 0.040 |
| 2026-04-01 | meninos | 2 | 23.810 | 0.289 | 0.161 | 0.189 | 0.033 |
| 2026-04-01 | oratorio | 1 | 23.170 | 0.249 | 0.223 | 0.164 | 0.094 |
| 2026-04-01 | tamanduatei | 8 | 23.170 | 0.292 | 0.148 | 0.149 | 0.038 |

## Controles e datas solicitadas

| data | grupo | bacia | max_dia | prob_perigoso_any | prob_saturante | prob_prolongada | prob_pancada |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-06-02 | controle_seco_2025 | guarara | 0.000 | 0.066 | 0.013 | 0.072 | 0.028 |
| 2025-06-02 | controle_seco_2025 | meninos | 0.000 | 0.102 | 0.016 | 0.083 | 0.024 |
| 2025-06-02 | controle_seco_2025 | oratorio | 0.000 | 0.101 | 0.025 | 0.103 | 0.025 |
| 2025-06-02 | controle_seco_2025 | tamanduatei | 0.000 | 0.067 | 0.018 | 0.074 | 0.047 |
| 2025-06-19 | controle_seco_2025 | guarara | 0.000 | 0.123 | 0.035 | 0.140 | 0.044 |
| 2025-06-19 | controle_seco_2025 | meninos | 0.000 | 0.047 | 0.013 | 0.061 | 0.032 |
| 2025-06-19 | controle_seco_2025 | oratorio | 0.000 | 0.197 | 0.054 | 0.174 | 0.058 |
| 2025-06-19 | controle_seco_2025 | tamanduatei | 0.000 | 0.131 | 0.031 | 0.124 | 0.057 |
| 2025-06-20 | controle_seco_2025 | guarara | 0.000 | 0.113 | 0.034 | 0.110 | 0.042 |
| 2025-06-20 | controle_seco_2025 | meninos | 0.000 | 0.042 | 0.013 | 0.049 | 0.030 |
| 2025-06-20 | controle_seco_2025 | oratorio | 0.000 | 0.237 | 0.054 | 0.204 | 0.056 |
| 2025-06-20 | controle_seco_2025 | tamanduatei | 0.000 | 0.131 | 0.054 | 0.121 | 0.057 |
| 2025-06-21 | controle_seco_2025 | guarara | 0.000 | 0.204 | 0.037 | 0.187 | 0.089 |
| 2025-06-21 | controle_seco_2025 | meninos | 0.000 | 0.050 | 0.017 | 0.055 | 0.031 |
| 2025-06-21 | controle_seco_2025 | oratorio | 0.000 | 0.276 | 0.067 | 0.265 | 0.056 |
| 2025-06-21 | controle_seco_2025 | tamanduatei | 0.000 | 0.152 | 0.065 | 0.132 | 0.093 |
| 2026-03-31 | checagem_2026_usuario | guarara | 0.980 | 0.123 | 0.092 | 0.144 | 0.057 |
| 2026-03-31 | checagem_2026_usuario | meninos | 1.970 | 0.124 | 0.056 | 0.133 | 0.038 |
| 2026-03-31 | checagem_2026_usuario | oratorio | 2.560 | 0.128 | 0.097 | 0.136 | 0.082 |
| 2026-03-31 | checagem_2026_usuario | tamanduatei | 1.180 | 0.149 | 0.063 | 0.150 | 0.102 |
| 2026-04-01 | checagem_2026_usuario | guarara | 23.170 | 0.236 | 0.291 | 0.198 | 0.040 |
| 2026-04-01 | checagem_2026_usuario | meninos | 23.810 | 0.289 | 0.161 | 0.189 | 0.033 |
| 2026-04-01 | checagem_2026_usuario | oratorio | 23.170 | 0.249 | 0.223 | 0.164 | 0.094 |
| 2026-04-01 | checagem_2026_usuario | tamanduatei | 23.170 | 0.292 | 0.148 | 0.149 | 0.038 |
| 2026-04-10 | checagem_2026_usuario | guarara | 3.540 | 0.102 | 0.066 | 0.109 | 0.027 |
| 2026-04-10 | checagem_2026_usuario | meninos | 2.950 | 0.065 | 0.022 | 0.088 | 0.022 |
| 2026-04-10 | checagem_2026_usuario | oratorio | 4.330 | 0.141 | 0.066 | 0.137 | 0.057 |
| 2026-04-10 | checagem_2026_usuario | tamanduatei | 4.330 | 0.139 | 0.042 | 0.077 | 0.039 |
| 2026-04-19 | checagem_2026_usuario | guarara | 0.200 | 0.158 | 0.019 | 0.135 | 0.057 |
| 2026-04-19 | checagem_2026_usuario | meninos | 0.000 | 0.302 | 0.104 | 0.241 | 0.076 |
| 2026-04-19 | checagem_2026_usuario | oratorio | 0.200 | 0.155 | 0.067 | 0.181 | 0.068 |
| 2026-04-19 | checagem_2026_usuario | tamanduatei | 0.200 | 0.115 | 0.028 | 0.081 | 0.039 |

## Datas sem dados para pontuação

| data | grupo | bacia | status | modelo | variante | train_policy | max_dia | acum_dia | acum_7d | acum_30d | n_chamados_validacao | prob_pancada | target_pancada | prob_prolongada | target_prolongada | prob_saturante | target_saturante | prob_perigoso_any | target_perigoso_any |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-07-01 | chamado_2026 | guarara | sem_dados |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 2026-07-01 | chamado_2026 | meninos | sem_dados |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 2026-07-01 | chamado_2026 | oratorio | sem_dados |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 2026-07-01 | chamado_2026 | tamanduatei | sem_dados |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 2026-12-01 | chamado_2026 | guarara | sem_dados |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 2026-12-01 | chamado_2026 | meninos | sem_dados |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 2026-12-01 | chamado_2026 | oratorio | sem_dados |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| 2026-12-01 | chamado_2026 | tamanduatei | sem_dados |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## Observação sobre estação vs bacia

O modelo produz probabilidade por bacia/contrato de estações, não uma probabilidade independente por estação. O arquivo `validacao_chamados_2026_risk_v1_station_rain.parquet` traz a chuva observada por estação para explicar cada score.
