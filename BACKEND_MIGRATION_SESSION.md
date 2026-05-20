# Sessao persistente: migracao backend para champion Open-Meteo + MinIO

Data inicial: 2026-05-17

Este documento registra a sessao de arquitetura e plano de migracao do backend. Ele fica na raiz do projeto porque o escopo agora e a aplicacao inteira, nao apenas a modelagem em `notebooks`.

## Objetivo

Migrar a aplicacao de predicao de enchente do fluxo legado para servir os novos champions:

- trocar OpenWeather por Open-Meteo como fonte principal de forecast;
- persistir forecast/historico operacional em MongoDB;
- trocar Google Drive por MinIO/S3 para artefatos e dumps;
- exportar modelos como pipeline completo com pre-processamento + predicao em `joblib` ou `pickle`;
- manter a API consumida pelo dashboard funcionando durante a transicao.

## Arquitetura alvo considerada

A arquitetura prevista no desenho do projeto separa quatro blocos principais:

1. `api_data`
   - Colecoes operacionais de dados meteorologicos.
   - `forecast`: alimentado hora em hora por um `ForecastClient`.
   - `historic`: alimentado diariamente por estacoes meteorologicas, com 24 requisicoes por dia.

2. `dump`
   - Job intermediario que exporta dados de `api_data` para MinIO.
   - Frequencia sugerida no desenho:
     - semanal para `forecast`;
     - diaria para `historic`.

3. MinIO
   - Armazena:
     - `modelos`: artefatos de modelos/pipelines;
     - `chamados`: dados de chamados usados em treino;
     - `ow data`: dumps historicos meteorologicos. O nome deve ser revisado para `weather-data` ou `openmeteo-data`, ja que a fonte nova sera Open-Meteo.

4. `models_db`
   - Banco de metadados e resultados de modelo.
   - `models`: configuracao de modelos, versoes, artefatos em MinIO e champion ativo.
   - `inference`: resultados servidos pelo backend para o dashboard.

Fluxos principais:

- `MinIO.weather/datasets -> bootstrap -> api_data`: arquivos historicos versionados populam MongoDB local/dev/prod.
- `ForecastClient -> api_data.forecast -> back`: o backend usa forecast operacional recente para inferencia.
- `estacoes meteorologicas -> api_data.historic`: base operacional/historica observada.
- `api_data -> dump -> MinIO`: materializa dados operacionais para treino/reprocessamento.
- `treinamento -> MinIO.modelos`: treinamento salva pipelines versionados.
- `treinamento -> models_db.models`: treinamento registra metadados e aponta o champion.
- `back -> models_db.models + MinIO.modelos`: backend descobre e carrega o artefato champion.
- `back -> models_db.inference -> dash`: inferencias ficam no MongoDB e sao lidas pelo dashboard.

Regra operacional central: **na hora da predicao, dados meteorologicos vêm do MongoDB**. MinIO nao e consultado pelo `FeatureAssembler` online; ele serve para bootstrap, backfill, dumps, datasets e artefatos.

## Estado atual observado no repositorio

### Backend

- `backend/harvest` coleta fontes configuradas em MongoDB (`harvest_config.sources` e `source_types`) e grava em `harvest_data`.
- `Harvester._build_source()` hoje so instancia `OpenWeatherSource`.
- `OpenWeatherSource` normaliza `hourly[].rain` e grava documentos com `dt_request`, `region`, `subregion` e `type`.
- `backend/floodcast`:
  - le configs de modelos em `floodcast.models`;
  - busca forecast horario em `harvest_data`;
  - baixa pipeline/explainer do Google Drive via `gdown`;
  - roda predicao;
  - grava `floodcast.inference`.
- `backend/sentry` expoe `GET /region/<region_name>` lendo `floodcast.inference`.
- Ja existe uso de MinIO no blueprint `chamados_pbi`, mas `floodcast` ainda nao usa MinIO.
- `docker-compose.yml` ainda nao sobe MinIO local.

### Modelagem

- O melhor estado recente usa target ordinal de severidade V7 e compara `H12/H24/H48` com features V4 + forecast.
- Champions registrados nos experimentos:
  - `guarara`: `H24_forecast`;
  - `meninos`: baseline `H12/H24` sem forecast;
  - `oratorio`: baseline `H12/H24` sem forecast;
  - `tamanduatei`: `H24_forecast`.
- Tentativas `rich` e `max` foram testadas e descartadas; `mean` continua sendo o teto aceito para forecast ERA5/Open-Meteo naquele experimento.
- Pendencia critica resolvida em 2026-05-19: features `api_070`, `api_085`, `api_095` nao usam mais `max_dia[t]`; o export atual aplica `shift(1)` antes do `lfilter`.

## Ajustes no plano apos considerar a arquitetura original

1. Separar melhor `api_data` de `models_db`.
   - O plano anterior falava genericamente em MongoDB. O desenho pede separacao clara:
     - dados meteorologicos operacionais em `api_data`;
     - modelos/inferencias em `models_db` ou o atual `floodcast`.

2. Manter `harvest` como coletor, mas talvez renomear conceitos.
   - O modulo atual `harvest` pode cumprir o papel de `ForecastClient` e coleta diaria de `historic`.
   - Se a arquitetura ficar mais explicita, criar jobs separados:
     - `forecast_collector`: hora em hora;
     - `historic_collector`: diario, 24 requisicoes;
     - `dump_weather_data`: diario/semanal para MinIO.

3. MinIO nao e so para modelos.
   - Tambem deve receber dumps de:
     - chamados;
     - forecast;
     - historico meteorologico.
   - Isso ajuda treino reprodutivel e reduz dependencia de consultas diretas ao Mongo.

4. O treinamento deve escrever dois destinos.
   - Artefatos grandes em MinIO.
   - Metadados/versionamento/champion em `models_db.models`.

5. O backend nao deve treinar nem montar dataset.
   - O backend deve:
     - ler metadados do champion;
     - carregar artefato do MinIO;
     - montar entrada operacional minima a partir de `api_data`;
     - gravar inferencia em `models_db.inference`.

## Decisoes propostas

1. Criar um contrato novo de dados meteorologicos para inferencia.
   - O runtime le **somente MongoDB** para montar features.
   - `api_data.historic` representa observacoes de estacoes meteorologicas, independentemente da origem inicial ser CEMADEN ou Defesa Civil.
   - Inicialmente, `api_data.historic` sera populado por bootstrap a partir de parquets CEMADEN no MinIO.
   - Depois, a API da Defesa Civil alimentara a mesma colecao para o mes corrente e periodos ainda nao publicados pelo CEMADEN.
   - `api_data.forecast` representa forecast Open-Meteo a partir da hora/data de predicao.

2. Criar `OpenMeteoSource` ou `OpenMeteoForecastClient`.
   - Pode morar inicialmente em `backend/harvest/harvest/sources/openmeteo_source.py`.
   - Deve persistir resposta normalizada, nao so payload bruto.
   - Campos horarios minimos:
     - `dt`;
     - `precipitation_mm`;
     - opcionalmente `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`, `precipitation_probability`.

3. Definir schema Mongo para `api_data`.
   - `api_data.forecast`: documentos por `dt_request`, ponto/bacia e provider.
   - `api_data.historic`: observacoes horarias das estacoes ou agregados por bacia.
   - Indices por `dt_request`, `provider`, `point_id`/`bacia`.

4. Definir layout MinIO.
   - Bucket candidato: `psa`.
   - Prefixos:
      - `models/`;
      - `datasets/`;
      - `weather/cemaden/`;
      - `weather/openmeteo/forecast/`;
      - `weather/openmeteo/history/` se historico de forecast for mantido;
      - `chamados/`;
      - `weather/openweather/legacy/` se for manter legado.

5. Exportar champion como artefato completo.
   - Deve conter pre-processamento, estimadores e thresholds.
   - Deve carregar em ambiente `floodcast` sem depender de codigo definido apenas em notebook.
   - Deve retornar severidade/probabilidades em contrato estavel.

6. Atualizar saida de inferencia sem quebrar dashboard.
   - Manter `predict`, `proba`, `explanation`, `rain_today` quando possivel.
   - Adicionar `severity` e `obj_version: "0.3"`.

## Plano de implementacao

### Fase 0 - Contrato operacional do champion ✅ CONCLUIDA (2026-05-19)

**Resumo:**
- **Leak corrigido:** `api_*` agora usa `max_dia.shift(1)` antes do `lfilter`, garantindo que a feature do dia `t` dependa apenas de dados ate `D-1`.
- **Script de exportacao:** `notebooks/scripts/tools/export_champion.py` treina 3 classificadores binarios (≥1, ≥2, ≥3) por bacia no dataset completo e exporta `.joblib` + `.json`.
- **Artefatos gerados:** 4 champions (`guarara`, `meninos`, `oratorio`, `tamanduatei`) em `notebooks/modelos/`.
- **Classe serializavel:** `ChampionOrdinalModel` em `backend/floodcast/floodcast/ordinal_model.py` com interface estavel (`predict`, `predict_proba`, `alarm_level`).
- **Smoke test backend:** 5/5 testes passando (`test_model_load.py` — 4 testes de interface + `test_model_regression.py` — 1 teste com dados reais do dataset guarara).
- **Reorganizacao do repo:** scripts separados em `pipeline/`, `experiments/`, `diagnostics/`, `tools/`; dados weather/resultados em subdiretorios; notebooks legados arquivados.

**Proximo passo:** Fase 1 (MinIO data lake + bootstrap MongoDB).

### Fase 1 - MinIO data lake + bootstrap MongoDB

Principio corrigido em 2026-05-19: **runtime de inferencia le apenas MongoDB**.

MinIO armazena arquivos grandes/versionados e serve como origem de bootstrap/backfill:

- modelos `.joblib` e metadados exportados;
- parquets historicos CEMADEN;
- parquets historicos/operacionais de forecast quando disponiveis;
- datasets de treino/reprocessamento.

MongoDB e a fonte operacional do backend:

- `api_data.historic`: observacoes de estacoes meteorologicas, inicialmente populadas por bootstrap a partir de CEMADEN no MinIO;
- `api_data.forecast`: forecast Open-Meteo, inicialmente populado por bootstrap/backfill e depois por collector operacional;
- no futuro, a API da Defesa Civil alimenta a mesma `api_data.historic`, substituindo/complementando o CEMADEN no mes corrente.

Tarefas:

- Subir MinIO local no `docker-compose.project.yml`.
- Criar bucket/prefixos:
  - `models/`;
  - `weather/cemaden/`;
  - `weather/openmeteo/forecast/`;
  - `datasets/`.
- Criar script idempotente `bootstrap_api_data`:
  - le parquets do MinIO;
  - popula `api_data.historic` com dados CEMADEN normalizados;
  - popula `api_data.forecast` com forecast historico/fixture quando existir;
  - cria indices;
  - usa upsert/dedup para poder rodar local/dev/prod sem duplicar dados.

Primeiros passos de implementacao:

1. **Infra local:** adicionar MinIO ao `docker-compose.project.yml` e variaveis `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`. ✅
2. **Cliente MinIO:** criar cliente simples para upload/download/listagem de objetos, usado por scripts e futuramente pelo `ArtifactLoader`. ✅
3. **Seeder de arquivos:** script local para enviar `notebooks/modelos/champion_*.joblib`, metadados `.json` e parquets CEMADEN/weather para os prefixos do bucket. ✅
4. **Bootstrap MongoDB:** script `bootstrap_api_data` que le do MinIO e faz upsert em `api_data.historic`/`api_data.forecast`. ✅
5. **Validacao objetiva:** teste ou smoke local conferindo contagem de documentos, indices criados e capacidade de buscar janela por bacia/data.

Schema inicial proposto:

- `api_data.historic`: um documento por leitura horaria de estacao meteorologica.
  - chave unica: `(provider, station_id, dt)`;
  - campos minimos: `provider`, `station_id`, `station_name`, `bacia`, `dt`, `precipitation_mm`, `source_file`, `loaded_at`.
- `api_data.forecast`: um documento por rodada de forecast por bacia/provider.
  - chave unica: `(provider, bacia, dt_request)`;
  - campos minimos: `provider`, `bacia`, `dt_request`, `timezone`, `hourly[]`, `source_file`, `loaded_at`.

### Fase 2 - FeatureAssembler lendo MongoDB

- Criar camada `WeatherDataRepository` para buscar janelas em `api_data.historic` e `api_data.forecast`.
- Criar `FeatureAssembler` para montar o DataFrame do champion V7 a partir exclusivamente do MongoDB.
- Preservar contrato de features exportado em `champion_*.json`.
- Testar montagem com fixtures pequenas sem depender de Docker.
- Testar integracao local com Mongo populado pelo bootstrap.

### Fase 3 - Registro de modelos + ArtifactLoader

- Definir schema de `models_db.models`.
- Campos minimos:
  - `name`;
  - `region`;
  - `subregion`/`bacia`;
  - `version`;
  - `is_champion`;
  - `artifact_uri`;
  - `feature_contract`;
  - `thresholds`;
  - `training_data_uri`;
  - `created_at`;
  - `metrics`.
- Atualizar script de export/registro para gravar artefato em MinIO e metadados no Mongo.
- Criar `ArtifactLoader` para MinIO/S3.
- Trocar `grab_from_gdrive()` por loader MinIO.

### Fase 4 - Backend `floodcast`

- Adaptar `ForecastLoader`/caso de uso para chamar `FeatureAssembler`.
- Adaptar `ModelPredictor` para artefato V7 ordinal.
- Adaptar `InferenceWriter` para `obj_version: "0.3"`.

### Fase 5 - Validacao local ponta a ponta

- Rodar Mongo + MinIO local.
- Popular `api_data` via `bootstrap_api_data`.
- Registrar um champion fake ou real em `models_db.models`.
- Executar `floodcast --date YYYY-MM-DD` como caminho one-shot sob demanda.
- Executar `floodcast-scheduler` com intervalo curto em modo teste e com alinhamento ao topo da hora em modo periodico real.
- Conferir `models_db.inference`.
- Conferir dashboard consumindo `/region/<region_name>`.

### Fase 6 - Estudo futuro de runtime performatico

- Estudar, fora do caminho critico da migracao inicial, se a inferencia pode ser servida por uma linguagem que gere executavel mais leve/perfomatico, como Go, C, C++ ou Rust.
- O ponto de partida deve ser o modelo Python ja estabilizado em producao.
- Investigar opcoes:
  - converter estimadores para ONNX e servir com ONNX Runtime;
  - separar feature engineering do model runner;
  - manter thresholds/metadados em JSON;
  - reimplementar apenas a camada de serving em linguagem compilada;
  - avaliar se o ganho de build/runtime compensa a complexidade.
- Premissa atual: `joblib` continua sendo artefato Python e nao sera servido diretamente por Go/C/C++/Rust no primeiro corte.

## Riscos e perguntas abertas

- O nome `ow data` do desenho deve ser atualizado para evitar confusao com OpenWeather.
- Para `meninos` e `oratorio`, os champions atuais nao usam forecast; precisamos decidir como isso opera sem usar dado observado do proprio dia.
- SHAP atual assume pipeline antigo com steps `aggregator` e `dt_dropper`; explicabilidade V7 precisa de outro desenho ou fica opcional no primeiro corte.
- Open-Meteo historico usado em treino e forecast operacional podem ter semanticas diferentes.
- Ainda falta decidir se `models_db` sera um banco novo ou se reaproveita o atual banco `floodcast`.

## Proxima acao recomendada

A Fase 0 esta concluida. O proximo passo tecnico deve ser a **Fase 1 — MinIO data lake + bootstrap MongoDB**:

1. Subir MinIO local e criar bucket/prefixos.
2. Colocar no MinIO os modelos e parquets historicos (CEMADEN e forecast historico/fixture quando existir).
3. Criar `bootstrap_api_data` para popular MongoDB a partir do MinIO.
4. Garantir que o backend de inferencia consulte apenas MongoDB para dados meteorologicos.

Motivo: o runtime correto nao deve ler Parquet/MinIO para montar features. MinIO e origem versionada para bootstrap/backfill; MongoDB e a fonte operacional.

## Sequencia de migracao local -> dev -> prod

Discussao registrada em 2026-05-17.

### Principio de ordem

A migracao deve reduzir risco em duas frentes separadas:

1. Risco de modelo: o novo champion precisa ser empacotado e reproduzir a inferencia esperada fora dos notebooks.
2. Risco de plataforma: MinIO, dumps, novos bancos/colecoes e ambientes cloud precisam funcionar sem quebrar o backend atual.

Como o maior risco funcional esta no contrato do modelo e nas features operacionais, o primeiro corte deve provar o novo modelo localmente com a menor mudanca de infraestrutura possivel. MinIO entra cedo para substituir Google Drive, mas o servico completo de dump pode entrar depois.

### Ordem recomendada

1. **Contrato e artefato do modelo local** ✅ concluido
   - Corrigir a definicao das features operacionais, especialmente API sem CEMADEN do dia atual.
   - Exportar um champion `joblib` completo para uma bacia.
   - Criar um teste/script local que carrega o artefato e roda inferencia para uma data conhecida.
   - Saida esperada: sabemos exatamente qual objeto o backend precisa montar para o modelo novo.

2. **MinIO data lake + bootstrap MongoDB**
   - Subir MinIO no `docker-compose`.
   - Criar bucket/prefixos `models/`, `weather/cemaden/`, `weather/openmeteo/forecast/`, `datasets/`.
   - Enviar artefatos champion e parquets historicos para MinIO.
   - Criar script idempotente para popular `api_data.historic` e `api_data.forecast` a partir do MinIO.
   - Criar indices Mongo e validar contagem/janelas carregadas.

3. **Leitura operacional local via MongoDB**
   - Criar `WeatherDataRepository` para consultar `api_data`.
   - Criar `FeatureAssembler` para montar features V7 exclusivamente a partir do MongoDB.
   - Rodar inferencia local ponta a ponta e gravar `models_db.inference`.

4. **Collectors operacionais e dumps**
   - Implementar `OpenMeteoSource`/collector para manter `api_data.forecast` atualizado.
   - Quando a API da Defesa Civil estiver disponivel, alimentar a mesma `api_data.historic`.
   - Implementar dumps de MongoDB para MinIO para treino/reprocessamento/reprodutibilidade.

5. **Ambiente dev na Saving Cloud**
   - Provisionar Mongo/MinIO dev ou apontar para servicos dev existentes.
   - Subir backend dev com variaveis S3/Mongo dev.
   - Rodar collectors dev.
   - Registrar champion dev em `models_db.models`.
   - Rodar inferencia diaria e backfills de datas conhecidas.
   - Comparar saida dev com resultados locais/notebooks.

6. **Homologacao**
   - Checklist minimo:
     - backend atual ainda responde `/region/<region_name>`;
     - inferencia nova grava `obj_version` novo sem quebrar dashboard;
     - logs de coleta Open-Meteo sem falhas recorrentes;
     - modelo carregado do MinIO, nao do Google Drive;
     - atualizacao/troca do modelo estado da arte possivel sem rebuild da aplicacao;
     - pelo menos alguns dias de inferencia dev comparados manualmente.

7. **Prod**
   - Subir infraestrutura MinIO/Mongo/config de prod.
   - Copiar artefatos aprovados do MinIO dev para prod ou promover por pipeline.
   - Registrar champion em `models_db.models` prod com `is_champion=true`.
   - Rodar em modo shadow inicialmente, se possivel:
     - inferencia nova gravando em colecao/campo separado;
     - dashboard ainda lendo saida antiga.
   - Depois virar leitura do dashboard para `obj_version` novo.

8. **Estudo pos-producao de runtime compilado**
   - Depois do modelo novo estabilizado em prod, estudar migracao da camada de serving para Go, C, C++ ou Rust.
   - Avaliar ONNX Runtime ou outro formato portavel para o estimador.
   - Essa etapa nao bloqueia a migracao Open-Meteo/MinIO.

### Decisao sobre o que vem primeiro

Entre "colocar MinIO com dump" e "colocar modelo novo com todas as logicas", a melhor primeira etapa e:

1. **modelo novo empacotado localmente**, para fechar contrato de features e saida;
2. **MinIO minimo para artefatos**, para remover Google Drive no caminho de inferencia;
3. **dump completo para MinIO** so depois.

Motivo: se o dump vier primeiro, podemos gastar tempo solidificando uma estrutura de dados que talvez mude quando corrigirmos API/features. Se o modelo vier primeiro sem nenhum MinIO, ainda ficamos presos ao Google Drive. O melhor meio-termo e provar o modelo e introduzir MinIO apenas no caminho de artefatos antes de expandir para dumps.

## Pendencia: arquitetura de dados para multiplos modelos

Discussao registrada em 2026-05-17.

O comportamento desejado nao e apenas rollback de modelo. O requisito correto e permitir **atualizacao e troca do modelo estado da arte sem rebuild da aplicacao**, incluindo disponibilizar novas versoes de modelos e selecionar outro modelo quando necessario.

Isso exige uma arquitetura de dados que nao fique presa ao formato fisico das colecoes MongoDB. O backend precisa conseguir buscar, a partir de um contrato de features do modelo, a janela de dados necessaria para inferencia.

Exemplo importante: o modelo atual pode precisar dos ultimos 30 dias de chuva para calcular features de acumulado/API. Outros modelos podem precisar de janelas diferentes ou combinacoes de forecast + historico observado.

Topico para discutir em fase propria:

- como representar o `feature_contract` de cada modelo;
- como consultar dados suficientes sem acoplar o modelo ao schema fisico do Mongo;
- como montar janelas de 30 dias, 72h, H24/H48 etc.;
- como lidar com modelos diferentes que exigem janelas diferentes;
- se o backend deve ter uma camada `WeatherDataRepository`/`FeatureDataProvider` independente da persistencia;
- como versionar dados de entrada usados em inferencias alternativas.

Decisao inicial:

- a primeira versao nao implementara um sistema completo de capabilities;
- cada modelo registrara uma `modeling_family`;
- atualizacoes sem rebuild serao aceitas apenas dentro de familias suportadas pelo runtime;
- o artefato precisa carregar e passar um smoke test com fixture da familia antes de ser promovido;
- se a validacao falhar, a versao anterior permanece ativa e a falha e registrada;
- capabilities/runtime contract ficam como melhoria desejavel se houver tempo.
