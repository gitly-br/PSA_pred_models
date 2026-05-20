# Relatório: Serving Validator — Combinador Mean + Piecewise Calibrado

**Data:** 2026-05-20  
**Script:** `notebooks/scripts/experiments/_serving_validator_risco_meteorologico.py`  
**Veredito:** `nao_servivel_ainda`

---

## 1. Objetivo

Validar se o candidato `combinador_mean` calibrado com `piecewise` pode virar artefato
servível no backend `floodcast` hoje, sem quebrar champions ou contratos existentes.

---

## 2. Interface Exigida pelo Backend

O `runner.py` consome modelos com a seguinte interface mínima:

| Método / Atributo | Tipo Esperado | Uso no Backend |
|-------------------|---------------|----------------|
| `model.predict(X)` | `array[int]` (0..3) | `predict_value = int(model.predict(X)[0])` |
| `model.predict_proba(X)` | `array[float]` shape `(n, 4)` | `raw_proba = float(model.predict_proba(X)[0][predict_value])` |
| `model.alarm_level(X)` | `array[int]` (0..3) | `severity_value = int(model.alarm_level(X)[0])` (fallback para predict) |
| `model.features` | `list[str]` | `X = feature_frame[features]` |
| `model.bacia` | `str` | Metadados |
| `model.modeling_family` | `str` | Metadados |
| `model.obj_version` | `str` | Metadados |

> **Nota:** O backend assume **sempre** 4 classes (`predict_proba` retorna matriz `(n, 4)`) e
> aplica calibração `isotonic` via `_apply_calibration(raw_proba, calibration)`.
> O candidato `combinador_mean` é um **score contínuo** [0,1], não um classificador ordinal.

---

## 3. Contrato de Entrada do Candidato

### 3.1 Features Requeridas

O candidato `combinador_mean` combina 6 componentes, cada um com seu próprio feature set.
O total auditado nos scripts experimentais é de **61 features/colunas**:

| Categoria | Features | Quantidade |
|-----------|----------|------------|
| CEMADEN passado (base V4) | `api_070/085/095`, `acc_6h_lag_1..12`, `max_day_lag1/2/3`, `mean_day_lag1`, `std_day_lag1`, `n_chovendo_max_lag1`, `pico_1h_lag1`, `horas_intensas_lag1`, `acum_7d`, `acum_30d`, `mes_sin`, `mes_cos` | 27 |
| CEMADEN derivadas (V2) | `acc_24h_lag1`, `acc_48h_lag1`, `razao_7d_30d`, `pico_vs_media`, `max_vs_media`, `tendencia_chuva`, `max_dia_rel`, `chuva_persistente`, `n_chovendo_lag2`, `n_chovendo_lag3`, `inter_max_acum7d`, `inter_max_std` | 11 |
| OpenWeather forecast history | `fc_rain_sum_h24/h48`, `fc_rain_max_h24/h48`, `fc_prob_mean_h24/h48`, `fc_prob_max_h24/h48`, `fc_temp_mean_h24/h48`, `fc_humidity_mean_h24/h48`, `fc_wind_max_h24/h48` | 16 |
| OpenMeteo multipoint (lag1) | `om_precip_sum_lag1`, `om_temp_max_lag1`, `om_temp_min_lag1`, `om_temp_mean_lag1`, `om_humidity_max_lag1`, `om_pressure_mean_lag1`, `om_wind_max_lag1` | 7 |
| Similaridade de perfis | `score_similaridade` (output de KMeans sobre vetor passado+futuro) | 1 (não-bruta) |
| **Total** | | **61** |

### 3.2 Janelas Históricas / Forecast

| Fonte | Janela | Detalhe |
|-------|--------|---------|
| CEMADEN histórico | 90 dias lookback | Montado pelo `FeatureAssembler` |
| OpenWeather forecast | H24 e H48 a partir do forecast emitido às 00:00 | **Não existe no backend** |
| OpenMeteo multipoint | Lag1 (dia anterior) + futuro 24/48/72h para similaridade | **Não existe no backend** |

### 3.3 Dados que Vêm do Mongo Hoje via `FeatureAssembler`

O `FeatureAssembler` monta **apenas** as 27 features V4 a partir do `WeatherDataRepository`,
que busca:
- `historic` collection (CEMADEN horário)
- `forecast` collection (OpenWeather pontual para `summarize_forecast`)

**Não monta:**
- Features derivadas V2 (são computáveis a partir dos dados que já existem, mas não implementadas)
- OpenWeather forecast history agregado por horizonte H24/H48
- OpenMeteo multipoint (ERA5/reanalise ou forecast)
- Similaridade de perfis (requer KMeans treinado + vetor futuro)

### 3.4 Dados que Ainda Não São Montados Hoje

Todas as **34 features faltantes** (61 - 27):

```
acc_24h_lag1, acc_48h_lag1, chuva_persistente,
fc_humidity_mean_h24, fc_humidity_mean_h48,
fc_prob_max_h24, fc_prob_max_h48, fc_prob_mean_h24, fc_prob_mean_h48,
fc_rain_max_h24, fc_rain_max_h48, fc_rain_sum_h24, fc_rain_sum_h48,
fc_temp_mean_h24, fc_temp_mean_h48, fc_wind_max_h24, fc_wind_max_h48,
inter_max_acum7d, inter_max_std, max_dia_rel, max_vs_media,
n_chovendo_lag2, n_chovendo_lag3,
om_humidity_max_lag1, om_precip_sum_lag1, om_pressure_mean_lag1,
om_temp_max_lag1, om_temp_mean_lag1, om_temp_min_lag1, om_wind_max_lag1,
pico_vs_media, razao_7d_30d, score_similaridade, tendencia_chuva
```

---

## 4. Serialização como Objeto com Interface Estável

### 4.1 Teste de Joblib

Foi criado um wrapper experimental `ServingRiskScoreModel` com:
- `predict` / `predict_proba` / `alarm_level`
- `risk_score` / `risk_components` / `profile`

**Resultado do teste:** 18/18 checks passaram:

| Check | Status |
|-------|--------|
| `has_predict` | OK |
| `has_predict_proba` | OK |
| `has_alarm_level` | OK |
| `has_features` | OK |
| `has_bacia` | OK |
| `has_modeling_family` | OK |
| `has_obj_version` | OK |
| `has_risk_score` | OK |
| `has_risk_components` | OK |
| `has_profile` | OK |
| `predict_shape_ok` | OK |
| `predict_range_ok` | OK |
| `proba_shape_ok` (n,4) | OK |
| `proba_sum_ok` (soma 1) | OK |
| `alarm_shape_ok` | OK |
| `risk_score_range_ok` ([0,1]) | OK |
| `risk_components_keys_ok` | OK |
| `profile_shape_ok` | OK |

> **Aviso:** O `predict_proba` do wrapper é **artificial** (heurística de distribuição
> proporcional ao score). Não representa probabilidades reais de severidade ordinal.
> Isso satisfaz o contrato sintático do backend, mas não o semântico.

### 4.2 Artefato Real Não Existe

O candidato `combinador_mean` não é um modelo único treinado. Ele é uma **média
pós-hoc** de 6 scores normalizados, gerada por script experimental. Para virar
artefato servível, seria necessário empacotar:

1. Os 6 sub-modelos treinados (LogisticRegression FC_ONLY, 2x GradBoost especialistas, GradBoost cauda, KMeans similaridade, etc.)
2. Os stats de normalização `min/max` por bacia (usados em `normalize_scores`)
3. O calibrador `piecewise` (parâmetros por bacia)
4. O wrapper com interface compatível

Nenhum artefato `.joblib` foi gerado na rodada experimental.

---

## 5. Proposta de `modeling_family` e `obj_version`

| Campo | Valor Proposto | Justificativa |
|-------|----------------|---------------|
| `modeling_family` | `psa_combinador_v1` | Família distinta do ordinal `psa_v7_ordinal`; indica ensemble de score contínuo |
| `obj_version` | `0.1-exp` | Versão experimental; não promete estabilidade de contrato até validação em shadow |

---

## 6. Mudanças Mínimas no Backend para Shadow Mode

Para servir o candidato em **shadow mode** (preservando `predict`, `severity`, `proba` dos champions atuais), as mudanças mínimas seriam:

### 6.1 FeatureAssembler (`feature_assembler.py`)
- Adicionar computação das **11 features derivadas CEMADEN** que são puramente transformações dos dados já disponíveis:
  - `acc_24h_lag1`, `acc_48h_lag1`, `razao_7d_30d`, `pico_vs_media`, `max_vs_media`, `tendencia_chuva`, `max_dia_rel`, `chuva_persistente`, `n_chovendo_lag2`, `n_chovendo_lag3`, `inter_max_acum7d`, `inter_max_std`
- **Impacto:** baixo; são expressões polars/pandas sobre dados existentes.

### 6.2 WeatherRepository (`weather_repository.py`)
- Adicionar `fetch_openweather_forecast_history(bacia, target_date, horizontes=[24,48])`
  - Agregar por janela H24/H48 o forecast emitido às 00:00.
- Adicionar `fetch_openmeteo_multipoint(bacia, target_date)`
  - Carregar pontos espaciais do bucket `weather/openmeteo_multipoint` e computar lag1.
- **Impacto:** médio; requer novas fontes de dados ou garantir que os dados já estejam em MinIO/Mongo.

### 6.3 Modelo Servível (novo arquivo, não altera champions)
- Criar `floodcast/combinador_model.py` com classe encapsulando:
  - 6 pipelines treinados
  - Normalização min/max por bacia
  - Calibrador piecewise (ou genérico)
  - Interface `predict`, `predict_proba`, `alarm_level`, `risk_score`, `risk_components`, `profile`
- **Impacto:** baixo (novo módulo, baixo acoplamento).

### 6.4 Runner (`runner.py`)
- Tornar a aplicação de calibração genérica (hoje suporta apenas `isotonic`):
  - `_apply_calibration` deve aceitar `piecewise`, `platt`, `quantile`, etc.,
    ou o modelo servível deve aplicar calibração internamente e expor `calibrated_proba`.
- Ou: o wrapper expõe `calibrated_proba` diretamente e o runner ignora calibração externa.
- **Impacto:** pequeno se for apenas generalizar `_apply_calibration`.

### 6.5 Model Registry (`model_registry.py`)
- Suportar campos extras no documento MongoDB:
  - `calibration.type`: `"piecewise" | "platt" | "isotonic" | ...`
  - `calibration.params`: dict com bins/edges/thresholds
- **Impacto:** pequeno (schema flexível em MongoDB).

### 6.6 Testes
- Adicionar teste de regressão para `combinador_model` em `backend/floodcast/tests/`.
- Garantir que champion `psa_v7_ordinal` continua passando.
- **Impacto:** baixo.

---

## 7. Veredito

### `nao_servivel_ainda`

**Blockers objetivos:**

| # | Blocker | Severidade |
|---|---------|------------|
| 1 | **34 features faltantes** no backend (56% do feature set do candidato) | Crítico |
| 2 | **Dados de forecast H24/H48 não são buscados nem montados** pelo backend hoje | Crítico |
| 3 | **Dados OpenMeteo multipoint não são buscados** | Crítico |
| 4 | **Componente de similaridade requer KMeans + OpenMeteo futuro**, não disponível | Crítico |
| 5 | **Calibrador `piecewise` não é suportado** pelo `_apply_calibration` do runner (apenas `isotonic`) | Alto |
| 6 | **Não existe artefato `.joblib`** do candidato; seria necessário reempacotar 6 modelos + stats + calibrador | Alto |
| 7 | **O candidato é score contínuo**, não classificador ordinal 0..3; o `predict_proba` artificial é um hack | Médio |

**Observação sobre resolução:**
Mesmo que todas as features fossem montadas, o score bruto do `combinador_mean`
raramente ultrapassa **0.60** no dataset histórico. Isso significa que qualquer
calibração monotônica tem dificuldade em atingir a faixa operacional `>70%`
para eventos fortes de forma consistente. O score é útil para **ranking relativo**
(comparar dias entre si), mas os thresholds absolutos de dashboard devem ser
interpretados com cautela até que o score bruto ganhe resolução na cauda.

---

## 8. Evidências

- Script de prova de contrato: `notebooks/scripts/experiments/_serving_validator_risco_meteorologico.py`
- Métricas de feature gap: 27/61 disponíveis, 34 faltantes
- Teste de serialização: 18/18 checks passaram (joblib + interface)
- Scores calibrados gerados: `notebooks/dados/results/calibracao_scores_serving.parquet`
- Parâmetros do calibrador: `notebooks/dados/results/calibracao_scores_serving_params.json`

---

## 9. Próximos Passos Recomendados (fora do escopo desta tarefa)

1. **Decidir se vale a pena** servir o combinador completo ou simplificar para
   apenas os componentes que usam dados já disponíveis (especialistas pancada/prolongada + cauda).
2. **Construir pipeline de feature engineering V2** no `FeatureAssembler` para
   as 11 derivadas CEMADEN.
3. **Avaliar se OpenWeather forecast history e OpenMeteo multipoint** estão
   disponíveis em produção (MinIO/Mongo) e criar repositórios para buscá-los.
4. **Gerar artefato `.joblib` real** com os 6 componentes treinados, stats de
   normalização e calibrador piecewise.
5. **Implementar shadow mode** registrando o artefato com `modeling_family="psa_combinador_v1"`
   e comparando `risk_score` com `raw_proba` do champion em dias subsequentes.
