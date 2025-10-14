# Este arquivo é responsável por registrar os blueprints da aplicação.
#
# O arquivo app.py chama a função register_app_blueprints(app) que registra os blueprints da aplicação.


from sanic import Blueprint

# Importacao dos blueprints
# Common Core Blueprints
from app.common.sanic_blueprints.exemplo_uso.feature_a import feature_a
from app.common.sanic_blueprints.exemplo_uso.feature_b import feature_b
from app.common.sanic_blueprints.server_health.health import health
from app.common.sanic_blueprints.exemplo_uso.json_validator import json_validator
from app.common.sanic_blueprints.exemplo_uso.redis_backs_integration import bp_redis_backs_integration



def register_common_core_blueprints(app):
    app.blueprint(health)
    app.blueprint(feature_a)
    app.blueprint(feature_b)
    app.blueprint(json_validator)
    app.blueprint(bp_redis_backs_integration)