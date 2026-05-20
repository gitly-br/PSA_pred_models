# Plano: Rollback Para V7

Objetivo: remover o champion sintetico atual `psa_risk_v1_station_contract_robust` do caminho de producao/local e restaurar um champion V7 confiavel, com validacao objetiva nas datas criticas.

## Contexto

- O registry atual aponta para `modeling_family = psa_risk_v1_station_contract_robust`.
- Mas os artefatos ativos `models/champion_*.joblib` carregam como `floodcast.ordinal_model.ChampionOrdinalModel`.
- Esses artefatos tem `metadata = {"generated_for_compose": True}`.
- Isso significa que o modelo ativo e sintetico/compativel, nao o robusto real.
- O robusto real existe como `models/psa_risk_v1_station_contract_robust.joblib`, mas nao carrega no runtime atual.
- O assembler atual tambem nao gera todas as features esperadas pelo robusto (`om_*`, `comp_*`, `acum_dia_lag1`), entao o runner preenche com `0.0`.

## Meta Do Rollback

- Restaurar V7 como champion ativo por bacia.
- Garantir que nenhum modelo com `metadata.generated_for_compose == True` fique ativo.
- Garantir que o contrato de probabilidade seja `proba` em escala `0..1`.
- Garantir que o front mostre percentual apenas formatando `proba * 100`.
- Validar que hoje/amanha e datas com chuva diferente nao resultem sempre em probabilidade alta identica.

## Etapa 1: Mapear Estado Atual

1. Listar documentos em `floodcast.models`:
   - `name`
   - `bacia`
   - `modeling_family`
   - `obj_version`
   - `artifact_uri`
   - `active`
   - `is_champion`
   - `features`
   - `thresholds`
   - `station_ids`

2. Listar objetos em MinIO sob `models/`.

3. Carregar cada `artifact_uri` ativo e imprimir:
   - classe Python
   - modulo
   - `modeling_family`
   - `obj_version`
   - `metadata`
   - `features` ou `all_feature_order`
   - se tem `risk_score`
   - se tem `predict_proba`
   - se tem `predict_severity`
   - se tem `compute_risk_components`

4. Confirmar explicitamente quais ativos sao sinteticos:
   - `getattr(model, "metadata", {}).get("generated_for_compose") is True`

## Etapa 2: Encontrar Ou Reconstruir V7

1. Procurar artefatos V7 existentes:
   - MinIO `models/`
   - repositorio local `**/*.joblib`
   - notebooks/resultados
   - scripts de seed/export antigos
   - commits anteriores se necessario

2. Procurar scripts relacionados:
   - `notebooks/scripts/experiments/_run_modelos_forecast_v7.py`
   - `notebooks/scripts/experiments/_run_modelos_forecast_v7_rich.py`
   - `notebooks/scripts/experiments/_run_modelos_v7.py`
   - `backend/floodcast/floodcast/ordinal_model.py`
   - `backend/floodcast/floodcast/seed_model_registry.py`

3. Determinar qual formato V7 o backend suporta:
   - idealmente `ChampionOrdinalModel`
   - metodos minimos:
   - `predict`
   - `predict_proba`
   - `alarm_level` ou `predict_severity`
   - `risk_score`
   - `features`

4. Se houver artefato V7 valido:
   - carregar localmente;
   - confirmar que as features esperadas sao geradas pelo `FeatureAssembler`;
   - subir para MinIO como `models/champion_<bacia>_v7.joblib`.

5. Se nao houver artefato V7 pronto:
   - reconstruir/exportar usando scripts V7 existentes;
   - empacotar como `ChampionOrdinalModel`;
   - registrar com `modeling_family = psa_v7_ordinal`.

## Etapa 3: Corrigir Seed/Registry

1. Alterar o seed para nunca promover modelo sintetico como champion em ambiente real.

2. Remover ou proteger este comportamento:

```python
if str(meta.get("modeling_family") or "") == "psa_risk_v1_station_contract_robust":
    model = _build_compatible_champion(meta, bacia)
```

3. Se for manter fallback sintetico para teste, exigir flag explicita, por exemplo:
   - `--allow-synthetic`
   - `ALLOW_SYNTHETIC_CHAMPION=true`

4. No registry, desativar os robustos sinteticos:
   - `active: false`
   - `is_champion: false`
   - ou mover para nome explicito `synthetic_*`

5. Registrar V7 por bacia:
   - `champion_guarara`
   - `champion_meninos`
   - `champion_oratorio`
   - `champion_tamanduatei`

Campos minimos:
- `name`
- `bacia`
- `region`
- `subregion`
- `artifact_uri`
- `features`
- `thresholds`
- `station_ids`
- `modeling_family = psa_v7_ordinal`
- `obj_version`
- `active = true`
- `is_champion = true`

## Etapa 4: Proteger Contrato De Features

1. No runner, antes de `_align_features`, detectar features ausentes.

2. Para rollback V7, aceitar somente se ausencias forem conhecidas e justificadas.

3. Para modelos novos, nao preencher silenciosamente `0.0` para features criticas.

4. Logar ou lancar erro se faltarem features do tipo:
   - `om_*`
   - `comp_*`
   - features explicitamente exigidas pelo modelo

Sugestao de regra:
- V7 pode usar fallback `0.0` apenas se o contrato antigo ja dependia disso.
- Robusto nao pode usar fallback silencioso.

## Etapa 5: Corrigir Probabilidade

1. Garantir que backend retorne:
   - `raw_proba` em `0..1`
   - `calibrated_proba` em `0..1`
   - `proba` em `0..1`

2. Remover multiplicacao por 100 do backend.

3. Front deve formatar:
   - `f"{proba * 100:.0f}%"`

4. Testar que `proba=0.83` aparece como `83%`, nao `8300%`.

## Etapa 6: Distribuicao De Chuva Por Periodo

1. Backend deve incluir no `forecast_summary`:

```json
"rain_by_period_mm": {
  "night": 0.0,
  "morning": 0.0,
  "afternoon": 0.0,
  "evening": 0.0
}
```

2. `rain_today` no payload deve representar acumulado de chuva por periodo, nao probabilidade escalada.

3. Front deve colorir madrugada/manha/tarde/noite com base em mm acumulado.

4. Nao usar `proba` para distribuir chuva por periodo.

## Etapa 7: Smoke Tests Obrigatorios

Rodar as datas:

- `2025-01-08`
- `2025-01-09`
- `2025-03-19`
- `2025-03-20`
- uma data sem chuva
- uma data com chuva fraca acima de `3.5mm`

Para cada data, limpar cache antes:

```bash
docker compose -f docker-compose.project.yml exec -T mongo mongosh -u psa -p psa --authenticationDatabase admin --quiet --eval 'db.getSiblingDB("floodcast").inference.deleteMany({region:"all", dt_key: {$gte: ISODate("YYYY-MM-DDT00:00:00.000Z"), $lt: ISODate("YYYY-MM-DD+1T00:00:00.000Z")}})'
```

Depois chamar:

```bash
curl -sS "http://127.0.0.1:8080/region/all?date=YYYY-MM-DD"
```

E tambem por bacia:

```bash
curl -sS "http://127.0.0.1:8080/region/guarara?date=YYYY-MM-DD"
curl -sS "http://127.0.0.1:8080/region/meninos?date=YYYY-MM-DD"
curl -sS "http://127.0.0.1:8080/region/oratorio?date=YYYY-MM-DD"
curl -sS "http://127.0.0.1:8080/region/tamanduatei?date=YYYY-MM-DD"
```

Registrar:
- `predict`
- `severity`
- `proba`
- `raw_proba`
- `calibrated_proba`
- `winner_region`
- `forecast_summary.total_mm`
- `forecast_summary.rain_by_period_mm`
- `rain_today`
- `models`

## Criterio De Aceitacao

- Nenhum champion ativo tem `metadata.generated_for_compose=True`.
- V7 carrega sem erro no runtime do `sentry`.
- `proba` fica em `0..1`.
- Front exibe percentual correto.
- Datas consecutivas nao ficam artificialmente identicas se forecast/historico mudarem.
- Dias secos ou chuva fraca nao viram risco critico automaticamente.
- `rain_today` reflete acumulado por periodo em mm.
- Testes unitarios relevantes passam.
- Smoke HTTP passa nas datas criticas.

## Comandos De Validacao Sugeridos

```bash
PYTHONPATH=. uv run --with motor --with joblib --with numpy --with pandas --with polars --with pytz --with scikit-learn --with pytest --env-file /dev/null pytest -q tests/test_runner_new.py tests/test_inference_writer.py tests/test_weather_repository.py tests/test_model_load.py
```

```bash
python -m py_compile frontend/app.py frontend/pages/home/home.py frontend/pages/home/utils.py
```

```bash
docker compose -f docker-compose.project.yml up -d --build --force-recreate sentry frontend
```

## Entregavel Final

O GPT-5.4 Mini deve devolver:

- o estado antes/depois do registry;
- quais artefatos V7 foram usados;
- evidencia de que nenhum sintetico ficou ativo;
- resultados das datas criticas em tabela;
- arquivos alterados;
- testes executados;
- decisao final: V7 aprovado temporariamente ou ainda precisa ajuste.
