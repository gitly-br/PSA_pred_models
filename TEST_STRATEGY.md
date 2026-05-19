# Estrategia de Testes

O objetivo dos testes e cobrir funcionalidades criticas e riscos operacionais. Cobertura de 100% nao e meta. Toda mudanca relevante deve demonstrar que preserva os contratos do sistema.

## Camadas de Teste

### Unitarios

Rodam sem Docker, MongoDB, MinIO ou APIs externas.

Devem cobrir:

- normalizacao de dados meteorologicos;
- validacao de dados suficientes;
- montagem de janelas/features quando possivel sem I/O;
- escolha de modelo estado da arte ou modelo especifico;
- construcao do objeto de inferencia;
- tratamento de erros conhecidos.

### Integracao

Rodam com servicos locais quando necessario, como MongoDB e MinIO.

Devem cobrir:

- escrita/leitura de forecast e historico no MongoDB;
- carregamento de artefato pelo MinIO;
- persistencia da inferencia com campos de auditabilidade;
- dump para Parquet/MinIO;
- comportamento de falhas criticas com servicos indisponiveis ou dados ausentes.

### Contrato de API

Devem cobrir:

- cache hit para consulta de inferencia;
- cache miss com inferencia sob demanda;
- dados insuficientes;
- selecao opcional de modelo;
- compatibilidade do contrato versionado.

### Performance

Devem validar N1 em ambiente dev/prod-like:

- cache hit: p95 <= 200 ms, desejavel <= 100 ms;
- cache miss com inferencia sob demanda: p95 <= 5 s, desejavel <= 2 s.

Os valores podem ser ajustados depois de medir baseline, mas qualquer mudanca deve ser registrada em `REQUIREMENTS.md`.

### Smoke Tests

Devem rodar em local/dev antes de promover para prod:

- backend sobe com configuracao do ambiente;
- MongoDB acessivel;
- MinIO acessivel;
- modelo estado da arte carregavel;
- inferencia para data fixture funciona;
- endpoint de consulta retorna resposta valida.

## Principios

- Testes unitarios nao devem depender de servicos externos.
- Testes de integracao devem ser separados dos unitarios.
- APIs externas devem ser mockadas em testes unitarios.
- Casos criticos precisam de pelo menos um teste de sucesso e um teste de falha.
- Bugs corrigidos devem ganhar teste de regressao.
- Tarefas de migracao devem comecar pelo teste ou pelo contrato testavel.

## Fixtures Minimas

Manter fixtures pequenas e versionadas:

- resposta Open-Meteo reduzida;
- resposta da API de estacoes meteorologicas quando disponivel;
- documento de modelo registrado;
- artefato de modelo dummy para testes de loader;
- dados meteorologicos suficientes para uma inferencia controlada;
- dados insuficientes para testar erro conhecido.

## Evidencia de Conclusao

Uma tarefa so deve ser marcada como concluida quando houver evidencia:

- testes relevantes passando;
- smoke test executado quando houver I/O ou API;
- justificativa explicita quando um teste automatico nao for viavel;
- checklist da tarefa atualizado.
