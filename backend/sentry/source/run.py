import os
import sys
#sys.path.insert(0, 'app')
import time
#time.sleep(0.1)
from functools import partial
import argparse
import multiprocessing
from sanic import Sanic
from sanic.worker.manager import WorkerManager
from sanic.worker.loader import AppLoader
# Do submódulo git
from app.common.app import create_app
from app.common.utils.log_config import setup_logger
from app.common.settings_and_secrets.load_config import load_config_from_mongo

# Definindo a aplicação de back, talvez vire um env no futuro
# "app_sanic, admin_sanic, back_mob_logger"
NAO_ESQUECAM_DE_ALTERAR_AQUI_PARA_SUA_APLICACAO = "psa_predictor"

# python run.py --env local
# python run.py --env dev
# python run.py --env prod
def get_args():
    parser = argparse.ArgumentParser(description="Execute o servidor em modo local (local), desenvolvimento (dev) ou producao (prod).")
    parser.add_argument("-e", "--env", default="none", choices=["dev", "prod", "local"], help="Define o ambiente de execucao: 'dev' para desenvolvimento ou 'prod' para producao.")
    args = parser.parse_args()
    return args.env

if __name__ == "__main__":
    env = get_args()

    # Se o ambiente não for informado, encerrar o processo
    if env == "none":
        print("Ambiente nao informado. Utilize o parametro --env para definir o ambiente de execucao.")
        sys.stdout.flush()
        sys.exit(1)

    # Escrever como vaviarel de ambiente
    os.environ['env'] = env
    os.environ['application'] = NAO_ESQUECAM_DE_ALTERAR_AQUI_PARA_SUA_APLICACAO
    success_log, init_logger = setup_logger(env=env, name_process="init_sanic")


    # Load Config do Settings and Secrets da Gitly
    version = os.environ.get('MONGO_GITLY_VERSION_SCHEMA', 1)
    g_settings = load_config_from_mongo(environment=env,
                                        version=version, logger=init_logger)

    # Verifica se conseguiu carregar as configuracoes corretamente
    if g_settings is None or isinstance(g_settings, dict) is False:
        init_logger.critical("[run] Não foi possível carregar as configurações do mongo central da Gitly.")
        sys.exit(1)

    g_settings["application"] = NAO_ESQUECAM_DE_ALTERAR_AQUI_PARA_SUA_APLICACAO
    init_logger.debug(f"[run] Configurações carregadas do mongo central da Gitly: \n{g_settings}")

    loader = AppLoader(factory=partial(create_app, env=env,
                                       application=NAO_ESQUECAM_DE_ALTERAR_AQUI_PARA_SUA_APLICACAO,
                                       settings=g_settings, logger=init_logger))
    try:
        app = loader.load()

        # Configurando o tempo limite do worker_ack
        WorkerManager.THRESHOLD = g_settings["SANIC_INIT"]["WMAN_THRESOULD"]

        # Configurando o numero de workers
        CPU_FACTOR = g_settings["SANIC_INIT"]["WORKERS_COUNT"]["CPU_MULT_FACTOR"]
        LESS_VALUE = g_settings["SANIC_INIT"]["WORKERS_COUNT"]["LESS_VALUE"]
        SOME_OFSET_VALUE = g_settings["SANIC_INIT"]["WORKERS_COUNT"]["SOME_OFSET_VALUE"]
        cpus = multiprocessing.cpu_count()
        workers_ = SOME_OFSET_VALUE + (cpus * CPU_FACTOR) - LESS_VALUE

        # Iniciando o Server
        l_host = g_settings["SANIC_INIT"]["RUN_PARAMETERS"]["HOST"]
        l_port = g_settings["SANIC_INIT"]["RUN_PARAMETERS"]["PORT"]
        l_debug = g_settings["SANIC_INIT"]["RUN_PARAMETERS"]["DEBUG"]
        l_access_log = g_settings["SANIC_INIT"]["RUN_PARAMETERS"]["ACCESS_LOG"]
        l_auto_reload = g_settings["SANIC_INIT"]["RUN_PARAMETERS"]["AUTO_RELOAD"]

        if env == "local":
            app.run(host=l_host, port=l_port, debug=l_debug, access_log=l_access_log, single_process=True, auto_reload=l_auto_reload)
            sys.exit(0)

        app.prepare(host=l_host, port=l_port, debug=l_debug, access_log=l_access_log,
                    workers= workers_, auto_reload=l_auto_reload)
        Sanic.serve(primary=app, app_loader=loader)
    except Exception as e:
        critical_message = f"[run] Erro ao iniciar o servidor: {str(e)}"
        init_logger.critical(critical_message)
