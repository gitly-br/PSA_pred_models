# Como rodar local

`docker compose up -d`

# Sobre API

Usando SANIC como framework, a aplicação roda a partir do arquivo run.py que puxará todas as configurações no arquivo app.py. Lá puxa as configurações e seta workers, valores de configuração.

## Common
O diretorio common é de onde o SANIC vai rodar as configuracoes ja valores pro proprio SANIC e cria objetos para fazer operação com MongoDB e Redis (mas creio que esse nao vai ser usado, veio junto com o template).

### Mongo
Caso precise ver como funcione o uso do objeto do mongo pegue [este arquivo](psa_models_back/source/app/common/sanic_blueprints/exemplo_uso/feature_a.py) caso precise ver todas as operações veja [esse arquivo](psa_models_back/source/app/common/db_ops/app_mongo_ops.py)

### Requests dentro dos endpoints.
Caso precise fazer requests para outras APIs, veja [esse arquivo](psa_models_back/source/app/utils/openweather.py). Nele mostra como chamamos o httpx client criado ao iniciar a aplicacao e como fazer requests. 

Mas para fins de exemplo seria algo assim sendo request o objeto que chamamos em um endpoint.
`await request.app.ctx.httpx_client.post(url, headers=headers, json=payload)`

## Endpoints

Para criar endpoints, crie um arquivo na pasta `psa_models_back/source/app/sanic_blueprints` com uma pasta e arquivo com mesmo nome. Exemplo: `psa_models_back/source/app/sanic_blueprints/feature_a/feature_a.py`
E apos isso adicione no [blueprint_register](psa_models_back/source/app/sanic_blueprints/blueprint_register.py) o blueprint criado (para esse caso pode adicionar diretamente sem fazer o esquema de iterar pelo dicionario).