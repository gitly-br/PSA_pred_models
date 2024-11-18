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
from app.common.sanic_listeners.startup import init_redis_and_mongo
from app.common.sanic_listeners.per_worker_resources import init_redis_con, init_mongo_con
from app.common.utils.log_config import setup_logger
from app.utils.openweather import get_openweather_api_data

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

    @app.main_process_start
    async def main_start(app, loop):

        success, main_process_logger = setup_logger(env=env, name_process="main_process_logger")
        if not success:
            print(f"Erro ao configurar o logger principal. Erro: {main_process_logger}")
            sys.exit(1)

        main_process_logger.info("[main_start] Starting Initialization")

        dbs_connected = False
        waiting_time_retry = 5
        # Irá aguardar o Redis e os Mongos estarem disponíveis para continuar
        main_process_logger.info("[main_start] Verificando se Mongo e Redis estão disponíveis.")
        while not(dbs_connected):
            # Por enquanto está apenas verificando se é possivel se conectar ao Redis e ao Mongo antes de
            # começar a rotina de inicialização individual de cada worker
            success, error_message = await init_redis_and_mongo(logger=main_process_logger, settings=settings)
            main_process_logger.debug("[main_start] %d - %s", success, error_message)

            if not success:
                main_process_logger.warning("[main_start] Bases nao encontradas: %s,", error_message)
                await asyncio.sleep(waiting_time_retry)
            else:
                dbs_connected = True

        main_process_logger.info("[main_start] Mongo e Redis estão acessiveis.")
        # Recursos estão disponíveis, então podemos continuar com a inicialização dos workers
        main_process_logger.info("[main_start] Iniciando configuração dos workers.")




    # Inicializa Conexões com Redis
    @app.before_server_start
    async def before_start_load_redis(app, loop):

        redis_connected = False
        
        waiting_time_retry = 5
        # get worker id from sanic or process id from os
        if not hasattr(app.ctx, 'logger'):
            process_id = os.getpid()
            _, worker_logger = setup_logger(env=env, name_process=f"w_{process_id}")
            app.ctx.worker_id = process_id
            app.ctx.logger = worker_logger

        if not hasattr(app.ctx, 'sett'):
            app.ctx.sett = deepcopy(settings)

        while not(redis_connected):
            # ALL REDIS CONNECTIONS FOR EACH WORKER
            sucess_dbs, conn_redis_obj, error_message = await init_redis_con(settings=app.ctx.sett)
            
            if sucess_dbs:
                app.ctx.redis_obj = conn_redis_obj
                redis_connected = True
            else:
                app.ctx.logger.error("[before_start_load_redis] Sem conexao com Redis. Erro: ", error_message)
                await asyncio.sleep(waiting_time_retry)

            # sucess_dbs, conn_redis_data_logger_obj, error_message = await init_redis_con(settings=app.ctx.sett,is_data_logger=True)
            # if sucess_dbs:
            #     app.ctx.redis_data_logger_obj = conn_redis_data_logger_obj
            #     redis_connected = True
            # else:
            #     app.ctx.logger.error("[before_start_load_redis] Sem conexao com Redis data logger. Erro: ", error_message)
            #     await asyncio.sleep(waiting_time_retry)



        app.ctx.logger.info("[before_start_load_redis] Redis conectado com sucesso. (Worker %s)", app.ctx.worker_id)
        
        # # Criar Corotina que irá ficar escutando a fila de webhook do Redis A
        # # server_num = 0 -> Servidor Redis Primario
        # asyncio.create_task(receive_update_from_redis(app, worker_id=app.ctx.worker_id, server_num=0 ))
        
        # # server_num = 1 -> Servidor Redis Secundario
        # asyncio.create_task(receive_update_from_redis(app, worker_id=app.ctx.worker_id, server_num=1 ))





    # Inicializa conexões com Mongo
    @app.before_server_start
    async def before_start_load_mongo(app, loop):

        if not hasattr(app.ctx, 'logger'):
            process_id = os.getpid()
            _, worker_logger = setup_logger(env=env, name_process=f"w_{process_id}")
            app.ctx.worker_id = process_id
            app.ctx.logger = worker_logger

        if not hasattr(app.ctx, 'sett'):
            app.ctx.sett = deepcopy(settings)

        mongo_connected = False
        while not(mongo_connected):
            # ALL MONGO CONNECTIONS FOR EACH WORKER
            success, conn_mongo, error_message = await init_mongo_con(minPoolSize=8, maxPoolSize=None,
                                                                      settings=app.ctx.sett)
            if success:
                app.ctx.mongo_obj = conn_mongo
                mongo_connected = True
            else:
                app.ctx.logger.error("[before_start_load_mongo] Sem conexao com Mongo. Erro: ", error_message)
                await asyncio.sleep(3)

            app.ctx.logger.info("[before_start_load_mongo] Mongo conectado com sucesso. (Worker %s)", app.ctx.worker_id)

#         # Aqui será o carregamento do suporte multi lingua
#         # filter_ = {}
#         # projection_ = {
#         #     "_id": 0,
#         #     "ui_admin": 0
#         # }
#         # success, conn_problem, docs, error_message = await app.ctx.mongo_obj.read_all('gmall', 'multi_lang_support_col', filter_, projection_)
#         # if not success:
#         #     logging.info("[Starting Workers] Mongo multi_lang Read Error: %s", error_message)
#         #     app.ctx.lang_loc = {}

#         # else:

#         #     app.ctx.lang_loc = {}
#         #     for doc in docs:
#         #         lang = doc['language_iso639'].lower()
#         #         loc = doc['country_i18n_l10n'].lower()
#         #         app.ctx.lang_loc[(lang,loc)] = deepcopy(doc)

#         #     # carregando alguns defaults
#         # app.ctx.lang_loc[('pt', None)] = app.ctx.lang_loc[('pt','br')]
#         # app.ctx.lang_loc[('en', None)] = app.ctx.lang_loc[('en','us')]

#         # # default de todos os idiomas
#         # app.ctx.lang_loc[(None, None)] = app.ctx.lang_loc[('en','us')]


    # Inicializa os recursos
    @app.before_server_start
    async def before_start_load_httpx_client(app, loop):

        read_timeout = 10
        write_timeout = 10
        connect_timeout = 5
        timeout = httpx.Timeout(connect_timeout, read=read_timeout, write=write_timeout)
        app.ctx.httpx_client = httpx.AsyncClient(http2=True, follow_redirects=True,
                                                 timeout=timeout, limits=httpx.Limits(max_keepalive_connections=100, max_connections=1000))

    @app.before_server_start
    async def call_api_scheduler(app, loop):
        loop.create_task(get_openweather_api_data(app, ''))

    # Finaliza os recursos
    @app.before_server_stop
    async def before_server_stop(app, loop):
        await app.ctx.redis_obj.close_all_connections()
        await app.ctx.mongo_obj.close_all_connections()
        await app.ctx.httpx_client.aclose()

    @app.exception(ValidationError)
    async def invalid_body(request, exception):
        return json({'erro' : 'Está faltando o corpo json com os campos obrigatórios!'}, 400)

    register_common_core_blueprints(app)
    register_app_blueprints(app, settings)
    return app
