# Requisitos do Sistema PSA

Este documento registra os requisitos consolidados para a migracao do backend de predicao de enchentes. O objetivo e guiar implementacao, testes e decisoes de arquitetura sem transformar o projeto em microsservicos distribuidos.

## Requisitos Funcionais

### F1. Ingestao meteorologica

O sistema deve coletar, carregar por bootstrap e persistir dados meteorologicos operacionais em MongoDB. Para inferencia em runtime, a fonte de dados meteorologicos deve ser o MongoDB:

- forecast, inicialmente via Open-Meteo;
- dados observados/historicos de estacoes meteorologicas, inicialmente carregados por bootstrap a partir de parquets CEMADEN no MinIO;
- dados observados futuros da Defesa Civil de Santo Andre, via API a ser fornecida, alimentando a mesma colecao operacional usada pelo CEMADEN;
- schemas separados para forecast e observado/historico.

### F2. Retencao e arquivamento

O sistema deve manter dados usados em inferencia no MongoDB por janelas configuraveis e manter dados versionados/arquivados em Parquet no MinIO.

MinIO deve servir como data lake e origem de bootstrap/backfill, nao como fonte online para montagem de features no backend.

Politica inicial a definir:

- `inference`: retencao longa no MongoDB, possivelmente 1 a 2 anos;
- `forecast`: retencao menor, possivelmente 3 a 6 meses;
- `historic`: retencao menor, possivelmente 3 a 6 meses;
- dados arquivados devem ser particionados de forma consultavel, provavelmente por tipo, ano/mes e regiao/bacia.

### F3. Gestao de modelos

O sistema deve armazenar artefatos de modelo no MinIO, registrar metadados no MongoDB e carregar o modelo estado da arte ou um modelo especifico quando solicitado.

O registro de modelo deve conter, no minimo:

- identificador do modelo;
- versao;
- familia de modelagem (`modeling_family`);
- regiao/bacia;
- URI/hash do artefato;
- metricas;
- contrato de features;
- status de modelo estado da arte.

### F4. Execucao de inferencia

O sistema deve executar inferencias agendadas ou sob demanda, validar se existem dados suficientes, usar cache quando aplicavel e persistir os resultados.

Regras principais:

- se a inferencia ja existir para data/regiao/modelo aplicavel, retornar cache;
- se nao existir, verificar se ha dados suficientes;
- se houver dados suficientes, gerar, persistir e retornar;
- se nao houver, retornar erro conhecido de dados insuficientes;
- inferencias com modelo alternativo nao devem sobrescrever a inferencia operacional principal.

### F5. API de inferencia

O sistema deve expor consulta de inferencia por regiao, data e opcionalmente modelo.

O contrato da API deve ser versionado e manter compatibilidade com consumidores existentes durante a migracao.

## Requisitos Arquiteturais

### A1. Execucao monolitica por Docker Compose

O sistema deve rodar em um unico ambiente Docker Compose em um no Docker Engine. A divisao entre modulos existe para reduzir acoplamento de codigo, nao para impor microsservicos distribuidos.

### A2. Baixo acoplamento interno

Os modulos devem se comunicar por contratos explicitos:

- API chama casos de uso, nao detalhes de modelo;
- scheduler e API reutilizam os mesmos casos de uso;
- model runner nao conhece HTTP;
- collectors nao conhecem inferencia;
- Mongo e MinIO ficam atras de repositorios/clientes;
- notebooks nao sao dependencia runtime.

### A3. Separacao treino/inferencia

Producao nao deve depender de notebooks nem executar treinamento. O registro de modelos sera manual ou assistido por script, CLI, notebook de exemplo ou procedimento documentado.

A publicacao automatica de modelos fica fora do escopo inicial porque os chamados ainda dependem de envio manual pela Defesa Civil.

### A4. Configuracao por ambiente

Local, dev e prod devem usar o mesmo codigo e preferencialmente a mesma imagem, mudando comportamento por variaveis de ambiente e configuracoes externas.

### A5. Scheduler versionado no codigo

Jobs agendados devem ser definidos no codigo do projeto, nao apenas em cron configurado manualmente no servidor.

O scheduler deve reutilizar os mesmos casos de uso da API e usar lock quando houver risco de execucao concorrente.

### A6. Atualizacao de modelo sem rebuild

O sistema deve permitir atualizar ou trocar o modelo estado da arte sem rebuild da aplicacao quando o novo artefato pertencer a mesma familia de modelagem suportada pelo runtime.

Isso inclui:

- publicar novo artefato no MinIO;
- registrar metadados no MongoDB;
- marcar nova versao como estado da arte;
- selecionar modelo especifico quando solicitado.

Etapa inicial:

- todo modelo registra `modeling_family`;
- promocao automatica so ocorre se a familia for suportada pelo runtime;
- artefato precisa carregar no runtime;
- artefato precisa passar smoke test de inferencia com fixture da familia;
- se a validacao falhar, a versao anterior permanece ativa e o sistema registra warning/erro;
- mudanca de familia de modelagem exige evolucao do backend ou aprovacao manual com validacao explicita.

Etapa desejavel, fora do caminho critico inicial:

- evoluir de `modeling_family` para `runtime_contract_version` e `required_capabilities`;
- validar automaticamente fontes, janelas, transformacoes e schema de saida exigidos pelo modelo.

### A7. Acesso a dados orientado por contrato de features

O backend nao deve ficar acoplado ao schema fisico do MongoDB para montar entradas de modelo.

Cada modelo deve declarar um contrato de features que permita ao backend saber quais janelas e fontes de dados sao necessarias, como ultimos 30 dias de chuva, H24, H48, forecast e historico observado.

## Requisitos Nao Funcionais

### N1. Performance da API de inferencia

Pai principal: F5.

Critérios iniciais:

- cache hit: p95 <= 200 ms, desejavel <= 100 ms;
- cache miss com inferencia sob demanda: p95 <= 5 s, desejavel <= 2 s.

Validacao:

- teste de performance em ambiente dev/prod-like;
- medir endpoint HTTP completo com volume representativo no MongoDB.

### N2. Observabilidade operacional

Pais principais: F1, F3, F4, F5.

O sistema deve emitir logs/eventos suficientes para diagnosticar execucao operacional.

Eventos minimos:

- coleta: fonte, janela, quantidade de registros, status e duracao;
- carregamento de modelo: modelo, versao, URI/hash, status e duracao;
- inferencia: regiao, data alvo, modelo, tipo de execucao, cache hit/miss, status e duracao;
- falhas conhecidas: `error_code`, motivo e contexto minimo.

Validacao:

- testes com captura de logs/eventos para cache hit, cache miss, dados insuficientes e falha de modelo;
- smoke test em dev.

### N3. Auditabilidade da inferencia

Pais principais: F3, F4.

Toda inferencia persistida deve conter metadados suficientes para explicar como foi gerada.

Campos minimos:

- regiao/bacia;
- data alvo;
- data/hora de execucao;
- tipo de execucao;
- modelo e versao;
- URI/hash do artefato;
- versao do schema de saida;
- referencias ou descricao da janela de dados de entrada;
- resultado.

Validacao:

- executar uma inferencia controlada e verificar se o documento salvo no MongoDB contem todos os campos obrigatorios com valores coerentes.

### N4. Tratamento explicito de falhas

Pais principais: F1, F2, F3, F4, F5.

Falhas conhecidas devem produzir erros claros e nao podem gerar inferencias falsas ou parciais.

Casos minimos:

- falha de API externa nao grava payload invalido;
- falha de upload para MinIO nao remove dados do MongoDB;
- modelo ausente no MinIO retorna erro claro;
- dados insuficientes nao rodam o modelo;
- erro de MongoDB nao e tratado como cache miss.

Validacao:

- testes com mocks/falhas controladas;
- testes de integracao para falhas criticas quando viavel.

## Matriz Funcional x Nao Funcional

| Funcional | NFRs associados |
|---|---|
| F1 Ingestao meteorologica | N2, N4 |
| F2 Retencao e arquivamento | N2, N4 |
| F3 Gestao de modelos | N2, N3, N4 |
| F4 Execucao de inferencia | N2, N3, N4 |
| F5 API de inferencia | N1, N2, N4 |

## Fora de Escopo Inicial

- Treinamento automatico em producao.
- Ingestao automatica de chamados da Defesa Civil.
- Publicacao automatica completa de modelos treinados.
- Serving em Go, C, C++ ou Rust.
- Conversao obrigatoria para ONNX.
- Arquitetura de microsservicos distribuidos.
