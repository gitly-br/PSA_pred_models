import os
import sys
import asyncio
import httpx
from copy import deepcopy
from sanic import Sanic, response
from sanic import Blueprint
from sanic_ext import Extend
from sanic_ext.exceptions import ValidationError
from sanic.response import json

# Importações do submódulo common

from app.common.utils.log_config import setup_logger

# Importação dos blueprints do submódulo common
from app.common.sanic_blueprints.blueprint_register import register_common_core_blueprints

# Este arquivo é responsável por registrar os blueprints da aplicação.
# Coloque seus blueprints na função register_app_blueprints(app) no arquivo blueprint_register.py
from app.sanic_blueprints.blueprint_register import register_app_blueprints


# Importação do update (velho webhook entre os serviços back_admin e back_app)
# from app.modules.service_update_coroutines.service_update import receive_update_from_redis

# pegar caminho relativo seguro a partir de onde esta o arquivo atual (app.py)
def create_app(env, application, settings, logger):
    # Nome da aplicação
    sanic_app_name = f"SANIC-{application}"
    sanic_app_name = sanic_app_name.replace('_', '-').upper()
    sys.stdout.flush()
    # Se vai ou não ter inspector
    has_inspector = settings["SANIC_INIT"]["INSPECTOR"]["ENABLE"]

    app = Sanic(sanic_app_name, inspector=has_inspector)

    # Atualização das configurações da aplicação
    config_update = {
        "INSPECTOR": settings["SANIC_INIT"]["INSPECTOR"]["ENABLE"],
        "INSPECTOR_HOST": settings["SANIC_INIT"]["INSPECTOR"]["HOST"],
        "INSPECTOR_PORT": settings["SANIC_INIT"]["INSPECTOR"]["PORT"],
        "INSPECTOR_API_KEY": settings["SANIC_INIT"]["INSPECTOR"]["API_KEY"],

        # Builting Health Check
        "HEALTH": settings["SANIC_INIT"]["HEALTH_MONITOR"]["HEALTH"],
        "HEALTH_ENDPOINT": settings["SANIC_INIT"]["HEALTH_MONITOR"]["HEALTH_ENDPOINT"],
        "HEALTH_MAX_MISSES": settings["SANIC_INIT"]["HEALTH_MONITOR"]["HEALTH_MAX_MISSES"],
        "HEALTH_MISSED_THRESHHOLD": settings["SANIC_INIT"]["HEALTH_MONITOR"]["HEALTH_MISSED_THRESHHOLD"],
        "HEALTH_MONITOR": settings["SANIC_INIT"]["HEALTH_MONITOR"]["HEALTH_MONITOR"],
        "HEALTH_REPORT_INTERVAL": settings["SANIC_INIT"]["HEALTH_MONITOR"]["HEALTH_REPORT_INTERVAL"],
        "HEALTH_URI_TO_INFO": "",
        "HEALTH_URL_PREFIX": settings["SANIC_INIT"]["HEALTH_MONITOR"]["HEALTH_URL_PREFIX"], # para bater na rota e verificar a saude dos workers

        "KEEP_ALIVE_TIMEOUT": settings["SANIC_INIT"]["WEB_SERVICE_CONFIG"]["KEEP_ALIVE_TIMEOUT"],
        "RESPONSE_TIMEOUT": settings["SANIC_INIT"]["WEB_SERVICE_CONFIG"]["RESPONSE_TIMEOUT"],
        "REQUEST_TIMEOUT": settings["SANIC_INIT"]["WEB_SERVICE_CONFIG"]["REQUEST_TIMEOUT"],

        "REQUEST_BUFFER_SIZE": settings["SANIC_INIT"]["WEB_SERVICE_CONFIG"]["REQUEST_BUFFER_SIZE"],
        "REQUEST_MAX_SIZE": settings["SANIC_INIT"]["WEB_SERVICE_CONFIG"]["REQUEST_MAX_SIZE"],
        "REQUEST_MAX_HEADER_SIZE": settings["SANIC_INIT"]["WEB_SERVICE_CONFIG"]["REQUEST_MAX_HEADER_SIZE"]
    }


    app.update_config(config_update)
    settings["application"] = application
    logger.info(f"[create_app] Configurações atualizadas: \n{config_update}")

    # Configuração focada no CORS
    app.config.CORS_AUTOMATIC_OPTIONS = True
    app.config.CORS_ORIGINS = settings["SANIC_INIT"]["CORS_ORIGINS"]

    Extend(app)

    if config_update["HEALTH"] and config_update["HEALTH_MONITOR"]:
        logger.info(f"[create_app] Configurações de Health Monitor ativas. Endpoint: {config_update['HEALTH_ENDPOINT']}")
    logger.info(f"[create_app] Configurações atualizadas: \n{config_update}")

    




    





    


    # Inicializa os recursos
    @app.before_server_start
    async def before_start_load_httpx_client(app, loop):

        read_timeout = 10
        write_timeout = 10
        connect_timeout = 5
        timeout = httpx.Timeout(connect_timeout, read=read_timeout, write=write_timeout)
        app.ctx.httpx_client = httpx.AsyncClient(http2=True, follow_redirects=True,
                                                 timeout=timeout, limits=httpx.Limits(max_keepalive_connections=100, max_connections=1000))

    # Finaliza os recursos
    @app.before_server_stop
    async def before_server_stop(app, loop):
        pass

    @app.exception(ValidationError)
    async def invalid_body(request, exception):
        return json({'erro' : 'Está faltando o corpo json com os campos obrigatórios!'}, 400)

    register_common_core_blueprints(app)
    register_app_blueprints(app, settings)
    return app

