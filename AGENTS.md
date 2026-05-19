# AGENTS

Este projeto deve evoluir com baixo acoplamento, testes criticos e validacao objetiva. Nao basta fazer o codigo funcionar; cada mudanca deve mover o sistema na direcao arquitetural definida.

## Fontes de Verdade

- `REQUIREMENTS.md`: requisitos funcionais, arquiteturais e nao funcionais.
- `TEST_STRATEGY.md`: como validar funcionalidades criticas.
- `PROJECT_STRUCTURE.md`: divisao do projeto e responsabilidades dos modulos.
- `BACKEND_MIGRATION_SESSION.md`: contexto e plano da migracao backend.

## Forma de Trabalho

1. Antes de implementar, mapear a tarefa para requisitos.
2. Quebrar trabalho relevante em checklist curto.
3. Para funcionalidades criticas, usar TDD ou definir primeiro o contrato testavel.
4. Preservar baixo acoplamento entre modulos.
5. Validar com teste, smoke test ou evidencia explicita.
6. So marcar tarefa como concluida depois da validacao.

## Regras de Arquitetura

- API chama casos de uso; nao chama detalhes de modelo diretamente.
- Scheduler e API devem reutilizar os mesmos casos de uso.
- Model runner nao conhece HTTP.
- Collectors nao conhecem inferencia.
- MongoDB e MinIO devem ficar atras de repositorios/clientes.
- Notebooks nao sao dependencia runtime.
- Configuracao local/dev/prod deve vir de variaveis de ambiente ou configuracao externa.

## Testes

- Cobertura de 100% nao e objetivo.
- Funcionalidades criticas precisam de testes relevantes.
- Testes unitarios nao dependem de Docker, MongoDB, MinIO ou APIs externas.
- Testes de integracao ficam separados.
- Bugs corrigidos devem ganhar teste de regressao.

## Definition of Done

Uma tarefa esta pronta quando:

- checklist especifico foi concluido;
- requisitos impactados continuam atendidos;
- testes/smoke tests relevantes passaram;
- falhas e limites conhecidos foram registrados;
- nao houve aumento desnecessario de acoplamento.
