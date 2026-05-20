# Estrutura do Projeto

Este documento descreve a divisao principal do PSA e as responsabilidades dos modulos. A separacao entre modulos busca reduzir acoplamento de codigo; ela nao implica arquitetura de microsservicos distribuidos.

## Visao Geral

- `backend/`: coleta, inferencia, persistencia e API.
- `frontend/`: dashboard e visualizacao para usuarios.
- `notebooks/`: exploracao, modelagem, avaliacao e geracao manual/assistida de artefatos.
- `docs/`: documentacao tecnica/publicavel do projeto.

## Backend

O backend e dividido em tres submodulos principais.

### `backend/harvest`

Responsabilidade: coletar dados externos e persistir dados operacionais.

Hoje:

- carrega configuracoes de fontes via MongoDB;
- instancia fontes como `OpenWeatherSource`;
- expoe CLI de seed para MinIO e bootstrap de `api_data`;
- coleta payloads externos;
- normaliza parte dos dados;
- grava em MongoDB.

Direcao alvo:

- incluir Open-Meteo como fonte de forecast;
- coletar dados observados de estacoes meteorologicas da Defesa Civil quando a API estiver disponivel;
- manter script de bootstrap/backfill que carrega historico CEMADEN do MinIO para `api_data.historic`;
- manter script de seed para popular MinIO a partir de parquets locais e artefatos exportados;
- manter collectors desacoplados de inferencia e API;
- alimentar `api_data.forecast` e `api_data.historic`.

Requisitos relacionados: F1, F2, N2, N4.

### `backend/floodcast`

Responsabilidade: motor de inferencia.

Hoje:

- le configuracao de modelos no MongoDB;
- busca forecast no MongoDB;
- baixa artefatos do Google Drive;
- carrega pipelines `joblib`;
- executa predicoes;
- grava resultados em `floodcast.inference`.

Direcao alvo:

- carregar artefatos do MinIO;
- identificar modelo estado da arte ou modelo especifico;
- validar `modeling_family`;
- montar entrada operacional a partir de dados meteorologicos lidos exclusivamente do MongoDB (`api_data.forecast` e `api_data.historic`);
- manter MinIO fora do caminho online de montagem de features, exceto para carregamento de artefatos de modelo;
- executar inferencia agendada via scheduler do Compose e sob demanda via comando one-shot;
- persistir inferencias auditaveis.

Requisitos relacionados: F3, F4, N2, N3, N4.

### `backend/sentry`

Responsabilidade: API HTTP servida para consumidores externos, incluindo dashboard.

Hoje:

- expõe rotas Sanic;
- `GET /region/<region_name>` consulta inferencias persistidas no MongoDB;
- algumas rotas acessam dados auxiliares.

Direcao alvo:

- manter contrato de API versionado;
- consultar inferencia por regiao/data/modelo;
- retornar cache quando existir;
- acionar caso de uso de inferencia sob demanda quando nao houver cache e houver dados suficientes;
- nao conhecer detalhes internos de modelo, MinIO ou feature engineering.

Requisitos relacionados: F5, F4, N1, N2, N4.

## Frontend

Responsabilidade: dashboard e experiencia de consulta dos usuarios.

O frontend deve consumir a API exposta pelo backend sem depender de detalhes internos de coleta, modelo ou armazenamento. Durante a migracao, o contrato de resposta deve permanecer compativel ou versionado.

Requisitos relacionados: F5, N1.

## Notebooks

Responsabilidade: pesquisa, exploracao, treinamento e avaliacao.

Os notebooks podem gerar modelos, metricas e relatorios, mas nao devem ser dependencia runtime do backend de producao.

Estrutura interna:

- `scripts/pipeline/` — fases de processamento (exploratoria, pluviometria, preprocessamento, modelagem, forecast);
- `scripts/experiments/` — rodadas de benchmark (`_run_modelos_*.py`);
- `scripts/diagnostics/` — analises exploratorias e validacoes (`_diagnostico_*.py`);
- `scripts/tools/` — utilitarios de download e import (`minio_import.py`, `_download_openmeteo_multipoint.py`);
- `dados/` — dados primarios, com subdiretorios `weather/`, `results/` e `chuva_bacias/`;
- `modelos/` — artefatos exportados (`.joblib`, `.pkl`) gerados pelo treinamento;
- `archive/` — notebooks legados preservados fora do caminho ativo.

Direcao alvo:

- manter notebooks como ambiente de modelagem;
- publicar modelos manualmente ou por script assistido;
- registrar artefatos e metadados fora do runtime de producao.

Requisitos relacionados: A3, F3.

## Fronteiras de Acoplamento

- `harvest` nao conhece inferencia.
- `floodcast` nao conhece HTTP.
- `sentry` nao conhece detalhes de modelagem.
- notebooks nao sao importados pelo backend em producao.
- MongoDB e MinIO devem ser acessados por clientes/repositorios, nao espalhados pela regra de negocio.

Essas fronteiras sao parte dos requisitos arquiteturais do projeto.
