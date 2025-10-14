import os
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from pymongo.errors import OperationFailure, AutoReconnect
from app.common.db_ops.bson_data import decode_bson


# Verificar a conexão e tentar reconectar caso necessário
async def check_mongo_connection(client_mongo:AsyncIOMotorClient=None)->bool:

    # Tenta verificar conexao
    try:
        response = await client_mongo.admin.command('ping')
        return response.get("ok") == 1
    except Exception as e:
        return False

# Criar conexão com o cluster mongo
async def create_mongo_connection(mongo_settings, minPoolSize=1, maxPoolSize=None, maxConnecting=10)->tuple[bool, AsyncIOMotorClient, str]:

    error_message = None
    url = f"{mongo_settings['PREFIX_STR_MONGO_BAI_MAN']}{mongo_settings['USER_MONGO_BAI_MAN_READER']}:{mongo_settings['PASS_MONGO_BAI_MAN_READER']}{mongo_settings['SUFIX_STR_MONGO_BAI_MAN']}"

    try:
        client_mongo = AsyncIOMotorClient(url, retryWrites=True, minPoolSize=minPoolSize, maxPoolSize=maxPoolSize,
                                    appname="micro_mongo_writer", maxConnecting=maxConnecting,
                                    retryReads=True, journal=False, readPreference="secondaryPreferred",
                                    document_class = dict, uuidRepresentation="standard")
        # Verificar a conexão
        response = await client_mongo.admin.command('ping')
        return response.get("ok") == 1, client_mongo, error_message
    except Exception as e:
        error_message = f"[create_mongo_connection] Não foi possível conectar ao MongoDB. Erro: {e} | URL: {url}"
        return False, None, error_message

# Tenta reconectar ao mongo
async def reconnect_mongo(client_mongo, mongo_settings, minPoolSize=1, maxPoolSize=None, maxConnecting=10)->tuple[bool, AsyncIOMotorClient, str]:
    
    error_message = None
    # verificar a conexão
    success = await check_mongo_connection(client_mongo=client_mongo)
    if not success:
        # se não conseguir, tenta reconectar
        try:
            await client_mongo.close()
        except Exception:
            pass
        success, client_mongo, error_message = await create_mongo_connection(mongo_settings=mongo_settings, minPoolSize=minPoolSize, maxPoolSize=maxPoolSize, maxConnecting=maxConnecting)
        if not success:
            return False, None, error_message
    
    return True, client_mongo, error_message

async def db_exists(client_mongo, db_name):
    dbs = await client_mongo.list_database_names()
    return db_name in dbs


async def collection_exists(client_mongo, db_name, collection_name):
    db = client_mongo[db_name]
    collections = await db.list_collection_names()
    return collection_name in collections

# Inserir um documento no mongo
async def insert_one_to_mongo(client_mongo, db_name, collection_name, document_or_bson)->tuple[bool, bool, str]: # success, connection_problem, error_message
    error_message = None
    try:
        if isinstance(document_or_bson, bytes):  # if it's BSON
            document = decode_bson(document_or_bson)
        elif isinstance(document_or_bson, dict):  # if it's already a dictionary
            document = document_or_bson
        else:
            raise ValueError(f"[insert_one_to_mongo] Tipo de documento não suportado: {type(document_or_bson)}")

        db = client_mongo[db_name]
        collection = db[collection_name]
        await collection.insert_one(document)
        return True, False, error_message
    except ValueError as e:
        # caso a conversão não de certo
        return False, False, f"[insert_one_to_mongo] {e}"
    # Erro de conexão, não conseguiu por que o servidor nao esta acessivel
    except (ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect) as e:
        error_message = f"[insert_one_to_mongo] Connection related error: {e}"
        return False, True, error_message
    except Exception as e:
        error_message = f"[insert_one_to_mongo] Erro ao inserir no MongoDB: {e}"
        return False, False, error_message
    
# Inserir um documento no mongo e retornar o id do documento
async def insert_one_to_mongo_and_return_id(client_mongo, db_name, collection_name, document_or_bson)->tuple[bool, bool, ObjectId, str]: # success, connection_problem, ObjectId, error_message
    error_message = None
    try:
        if isinstance(document_or_bson, bytes):  # if it's BSON
            document = decode_bson(document_or_bson)
        elif isinstance(document_or_bson, dict):  # if it's already a dictionary
            document = document_or_bson
        else:
            raise ValueError(f"[insert_one_to_mongo_and_return_id] Tipo de documento não suportado: {type(document_or_bson)}")

        db = client_mongo[db_name]
        collection = db[collection_name]
        result = await collection.insert_one(document)
        return True, False, result.inserted_id, error_message
    except ValueError as e:
        # caso a conversão não de certo
        return False, False, None, f"[insert_one_to_mongo_and_return_id] {e}"
    # Erro de conexão, não conseguiu por que o servidor nao esta acessivel
    except (ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect) as e:
        error_message = f"[insert_one_to_mongo_and_return_id] Connection related error: {e}"
        return False, True, None, error_message
    except Exception as e:
        error_message = f"[insert_one_to_mongo_and_return_id] Erro ao inserir no MongoDB: {e}"
        return False, False, None, error_message

# Inserir um documento no mongo
async def insert_many_to_mongo(client_mongo, db_name, collection_name, document_or_bson_list)->tuple[bool, bool, str]: # success, connection_problem, error_message
    error_message = None
    try:
        if isinstance(document_or_bson_list, bytes):  # if it's BSON
            document_list = decode_bson(document_or_bson_list)
        elif isinstance(document_or_bson_list, list):  # if it's already a dictionary
            document_list = document_or_bson_list
        else:
            raise ValueError(f"[insert_many_to_mongo] Tipo de documento não suportado: {type(document_or_bson_list)}")

        db = client_mongo[db_name]
        collection = db[collection_name]
        await collection.insert_many(document_list)
        return True, False, error_message
    except ValueError as e:
        # caso a conversão não de certo
        return False, False, f"[insert_many_to_mongo] {e}"
    # Erro de conexão, não conseguiu por que o servidor nao esta acessivel
    except (ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect) as e:
        error_message = f"[insert_many_to_mongo] Connection related error: {e}"
        return False, True, error_message
    except Exception as e:
        error_message = f"[insert_many_to_mongo] Erro ao inserir no MongoDB: {e}"
        return False, False, error_message

# lê um documento do mongo
# CASO NÃO ENCONTRE NENHUM DOCUMENTO, RETORNA [] (lista vazia)
async def find_all_from_mongo(client_mongo, db_name, collection_name, filter_or_bson, projection=None, sort=None, limit=None): # success, connection_problem, data, error_message
    error_message = None
    
    # Deserializing filter if it's BSON
    if isinstance(filter_or_bson, bytes):
        try:
            filter_data = decode_bson(filter_or_bson)
        except Exception as e:
            error_message = f"[find_all_from_mongo] {e}"
            return False, False, [], error_message
    elif isinstance(filter_or_bson, dict):
        filter_data = filter_or_bson
    else:
        error_message = f"[find_all_from_mongo] Tipo de filtro não suportado: {type(filter_or_bson)}"
        return False, False, [], error_message

    try:
        db = client_mongo[db_name]
        collection = db[collection_name]
        cursor = collection.find(filter_data, projection, sort=sort, limit=limit)
        results = await cursor.to_list(length=None)
        return True, False, results, error_message
    except (OperationFailure, ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect) as e:
        error_message = f"[find_all_from_mongo] {e}"
        return False, True, [], error_message
    except Exception as e:
        error_message = f"[find_all_from_mongo] Erro ao ler do MongoDB: {e}"
        return False, False, [], error_message

async def find_one_from_mongo(client_mongo, db_name, collection_name, filter_or_bson, projection=None): # success, connection_problem, data, error_message
    error_message = None

    # Deserializing filter if it's BSON
    if isinstance(filter_or_bson, bytes):
        try:
            filter_data = decode_bson(filter_or_bson)
        except Exception as e:
            error_message = f"[find_one_from_mongo] {e}"
            return False, False, None, error_message
    elif isinstance(filter_or_bson, dict):
        filter_data = filter_or_bson
    else:
        error_message = f"[find_one_from_mongo] Tipo de filtro não suportado: {type(filter_or_bson)}"
        return False, False, None, error_message

    try:
        db = client_mongo[db_name]
        collection = db[collection_name]
        result = await collection.find_one(filter_data, projection)
        return True, False, result, error_message
    except (OperationFailure, ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect) as e:
        error_message = f"[find_one_from_mongo] {e}"
        return False, True, None, error_message
    except Exception as e:
        error_message = f"[find_one_from_mongo] Erro ao ler do MongoDB: {e}"
        return False, False, None, error_message

async def update_in_mongo(client_mongo, db_name, collection_name, filter_or_bson,updatedata_or_bson, operator="$set", upsert=True) -> tuple[bool, bool, str]: # success, connection_problem, error_message
    error_message = None
    try:
        # Deserializando filtro
        if isinstance(filter_or_bson, bytes):
            filter_data = decode_bson(filter_or_bson)
        elif isinstance(filter_or_bson, dict):
            filter_data = filter_or_bson
        else:
            raise ValueError(f"[update_in_mongo] Tipo de filtro não suportado: {type(filter_or_bson)}")
        
        # Deserializando dados de atualização
        if isinstance(updatedata_or_bson, bytes):
            update_data = decode_bson(updatedata_or_bson)
        elif isinstance(updatedata_or_bson, dict):
            update_data = updatedata_or_bson
        else:
            raise ValueError(f"[update_in_mongo] Tipo de dados de atualização não suportado: {type(updatedata_or_bson)}")

    # Se chegou aqui, tudo certo com o filtro e com os dados a serem atualizados
        db = client_mongo[db_name]
        collection = db[collection_name]
        await collection.update_one(filter_data, {operator: update_data}, upsert=upsert)
        return True, False, error_message
    except ValueError as e:
        # caso a conversão não de certo
        return False, False, f"[update_in_mongo] {e}"
    # Erro de conexão, não conseguiu por que o servidor nao esta acessivel
    except (ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect) as e:
        error_message = f"[update_in_mongo] Connection related error: {e}"
        return False, True, error_message
    except Exception as e:
        error_message = f"[update_in_mongo] Erro ao inserir no MongoDB: {e}"
        return False, False, error_message


async def update_many_in_mongo(client_mongo, db_name, collection_name, filter_or_bson,updatedata_or_bson, operator="$set", upsert=True) -> tuple[bool, bool, str]: # success, connection_problem, error_message
    error_message = None
    try:
        # Deserializando filtro
        if isinstance(filter_or_bson, bytes):
            filter_data = decode_bson(filter_or_bson)
        elif isinstance(filter_or_bson, dict):
            filter_data = filter_or_bson
        else:
            raise ValueError(f"[update_in_mongo] Tipo de filtro não suportado: {type(filter_or_bson)}")
        
        # Deserializando dados de atualização
        if isinstance(updatedata_or_bson, bytes):
            update_data = decode_bson(updatedata_or_bson)
        elif isinstance(updatedata_or_bson, dict):
            update_data = updatedata_or_bson
        else:
            raise ValueError(f"[update_in_mongo] Tipo de dados de atualização não suportado: {type(updatedata_or_bson)}")

    # Se chegou aqui, tudo certo com o filtro e com os dados a serem atualizados
        db = client_mongo[db_name]
        collection = db[collection_name]
        await collection.update_many(filter_data, {operator: update_data}, upsert=upsert)
        return True, False, error_message
    except ValueError as e:
        # caso a conversão não de certo
        return False, False, f"[update_in_mongo] {e}"
    # Erro de conexão, não conseguiu por que o servidor nao esta acessivel
    except (ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect) as e:
        error_message = f"[update_in_mongo] Connection related error: {e}"
        return False, True, error_message
    except Exception as e:
        error_message = f"[update_in_mongo] Erro ao inserir no MongoDB: {e}"
        return False, False, error_message


async def find_and_delete_from_mongo(client_mongo, db_name, collection_name, filter_or_bson, projection=None):
    error_message = None
    
    # Deserializing filter if it's BSON
    if isinstance(filter_or_bson, bytes):
        try:
            filter_data = decode_bson(filter_or_bson)
        except Exception as e:
            error_message = f"[find_and_delete_from_mongo] {e}"
            return False,False, None, error_message
    elif isinstance(filter_or_bson, dict):
        filter_data = filter_or_bson
    else:
        error_message = f"[find_and_delete_from_mongo] Tipo de filtro não suportado: {type(filter_or_bson)}"
        return False,False, None, error_message

    try:
        db = client_mongo[db_name]
        collection = db[collection_name]
        # Using find_one_and_delete
        result = await collection.find_one_and_delete(filter_data, projection=projection)
        
        return True, False, result, error_message
    except (OperationFailure, ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect) as e:
        error_message = f"[find_and_delete_from_mongo] {e}"
        return False, True, None, error_message
    except Exception as e:
        error_message = f"[find_and_delete_from_mongo] Erro ao ler do MongoDB: {e}"
        return False, False, None, error_message


# Fecha a conexão com o mongo usando o Motor da forma correta
async def close_mongo_connection(client_mongo):
    try:
        await client_mongo.close()
    except Exception:
        pass