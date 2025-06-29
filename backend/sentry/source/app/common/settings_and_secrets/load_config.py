from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from logging import Logger
import os
import json
from pathlib import Path


def load_config_from_mongo(environment:str, version:int, logger:Logger):

    mongo_connection_string = os.environ.get('MONGO_GITLY_CONNECTION_STRING', None)
    if version is None:
        version = os.environ.get('MONGO_GITLY_VERSION_SCHEMA', 1)

    # pegar o caminho do arquivo local load_config.py, para pegar a passta raiz e criar ou ler o arquivo settings_and_secrets.py do mesmo caminho
    # __file__ é o caminho do arquivo atual
    path_folder = Path(__file__).parent.absolute()
    file_secrets = path_folder / "settings_and_secrets.py"

    if mongo_connection_string is not None:
        client = MongoClient(mongo_connection_string, server_api=ServerApi('1'))
        db = client.gitly_set_and_sec  # Nome do seu banco de dados
        collection = db.psa_predictor  # Nome da sua coleção

        try:

            filter_ = {"ENV": environment, "SCHEMA_VERSION": version}
            proj_ = {"_id": 0, "env": 0, "SCHEMA_VERSION": 0}
            specific_data = collection.find_one(filter_, proj_)

            # "all" pois serve para todos os ambientes
            filter_ = {"ENV": "all", "SCHEMA_VERSION": version}
            proj_ = {"_id": 0, "env": 0, "SCHEMA_VERSION": 0}
            parameters_data = collection.find_one(filter_, proj_)

            if specific_data and parameters_data:
                config_data = parameters_data | specific_data
                with open(file_secrets, 'w') as file:
                    json.dump(config_data, file)
                return config_data
            else:
                if logger is not None:
                    logger.error("Não encontrou configuração no mongo. Irá tentar carregar arquivo local.")
                else:
                    print("Não encontrou configuração no mongo. Irá tentar carregar arquivo local.")
        except Exception as e:
            if logger is not None:
                logger.error(f"Erro ao acessar o mongo: {e}")
                logger.error(f"Tentando carregar arquivo local.")
            else:
                print(f"Erro ao acessar o mongo: {e}")
                print(f"Tentando carregar arquivo local.")

    else:
        if logger:
            logger.error("Não encontrou string de conexão MONGO_GITLY_CONNECTION_STRING no ambiente. Irá tentar carregar arquivo local.")
        else:
            print("Não encontrou string de conexão MONGO_GITLY_CONNECTION_STRING no ambiente. Irá tentar carregar arquivo local.")
    
    # Fallback para configuração local ou criação do arquivo se ele não existir
    try:
        with open(file_secrets, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        if logger:
            logger.error(f"Arquivo {file_secrets} não encontrado.")
        else:
            print(f"Arquivo {file_secrets} não encontrado.")

        return None
