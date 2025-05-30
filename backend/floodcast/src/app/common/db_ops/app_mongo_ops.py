# Abstração a nivel de aplicação
# Esse arquivo é a abstração das operações do comuns utilizadas pelo app no mongo
import sys
from copy import deepcopy
from app.common.db_ops.mongo_ops import *



class MongoAppOps:

    def __init__(self, settings:dict):

        type_of_back = settings.get("application")
        self.__mongo_settings = deepcopy(settings["MONGO_BACK"])
        self.status = "No Connections"
        self.__conn = [False, None]
        self.min_pool_size = self.__mongo_settings.get("MIN_POOL_SIZE", 10)
        self.max_pool_size = self.__mongo_settings.get("MAX_POOL_SIZE", None)
        self.max_connecting = self.__mongo_settings.get("MAX_CONNECTING", 40)


    def __enter__(self):
        return self

    async def __exit__(self, exc_type, exc_val, exc_tb):
        await self.close_all_connections()
        
    # fecha todas as conexões
    async def close_all_connections(self):
        await close_mongo_connection(self.__conn[1])
        self.__conn = [False, None]

    # Check the connection and try to reconect if needed
    async def check_and_retry_connection(self)-> tuple[bool, str]:

        if await check_mongo_connection(self.__conn[1]):
            return True, None
        
        await self.close_all_connections()  
        # Se não está ativa, tenta criar uma nova
        success, mongo_client, error_message = await create_mongo_connection(minPoolSize=self.min_pool_size,
                                                                       maxPoolSize=self.max_pool_size,
                                                                       maxConnecting=self.max_connecting,
                                                                       mongo_settings=self.__mongo_settings)
        self.__conn = [success, mongo_client]
        return success, error_message


    # inicializa a conexão com o mongo
    async def init_connection(self, minPoolSize=None, maxPoolSize=None)-> tuple[bool, str]:
        # Se a conexão já está ativa, não precisamos fazer nada
        if await check_mongo_connection(self.__conn[1]):
            return True, None
        
        # Se não está ativa, tenta criar uma nova
        await self.close_all_connections()
        min_pool_size = minPoolSize if minPoolSize else self.min_pool_size
        max_pool_size = maxPoolSize if maxPoolSize else self.max_pool_size
        sucess, mongo_client, error_message = await create_mongo_connection(minPoolSize=min_pool_size,
                                                                        maxPoolSize=max_pool_size,
                                                                        maxConnecting=self.max_connecting,
                                                                        mongo_settings=self.__mongo_settings)

        self.__conn = [sucess, mongo_client]
        return sucess, error_message
    

    # escreve um documento no mongo, com retentativa, nao aumente pois o mongo já faz isso por padrão
    async def write_one(self, db_name, col, doc) -> tuple[bool, bool, str]:
        if not self.__conn[0]: # verifica se possivelmente tem conexão
            success, error_message = await self.check_and_retry_connection()
            if not success:
                error_message = f"[write_one] Erro ao escrever no mongo: {error_message}"
                return False, True, error_message

        success, conn_problem, error_message = await insert_one_to_mongo(client_mongo=self.__conn[1],
                                                                        db_name=db_name, collection_name=col,
                                                                        document_or_bson=doc)

        return success, conn_problem, error_message
    
    # escreve um documento e retorna o id do documento
    async def write_one_and_return_id(self, db_name, col, doc) -> tuple[bool, bool, str, str]:
        if not self.__conn[0]: # verifica se possivelmente tem conexão
            success, error_message = await self.check_and_retry_connection()
            if not success:
                error_message = f"[write_one_and_return_id] Erro ao escrever no mongo: {error_message}"
                return False, True, None, error_message
            
        success, conn_problem, id_doc, error_message = await insert_one_to_mongo_and_return_id(client_mongo=self.__conn[1],
                                                                                              db_name=db_name, collection_name=col,
                                                                                              document_or_bson=doc)
        
        return success, conn_problem, id_doc, error_message
    
    # escreve vários documentos no mongo, com retentativa, nao aumente pois o mongo já faz isso por padrão
    async def write_many(self, db_name, col, doc) -> tuple[bool, bool, str]:
        if not self.__conn[0]: # verifica se possivelmente tem conexão
            success, error_message = await self.check_and_retry_connection()
            if not success:
                error_message = f"[write_one] Erro ao escrever no mongo: {error_message}"
                return False, True, error_message

        success, conn_problem, error_message = await insert_many_to_mongo(client_mongo=self.__conn[1],
                                                                        db_name=db_name, collection_name=col,
                                                                        document_or_bson_list=doc)

        return success, conn_problem, error_message
    
    # Lê todos os documentos de uma collection
    async def read_all(self, db_name, col, filter_={}, projection={}, sort=None, limit=0) -> tuple[bool, bool, list, str]:
        if not self.__conn[0]: # verifica a conexão
            success, error_message = await self.check_and_retry_connection()
            if not success:
                error_message = f"[read_all] Erro ao ler do mongo: {error_message}"
                return False, True, error_message
            
        success, conn_problem, values_list, error_message = await find_all_from_mongo(client_mongo=self.__conn[1],
                                                                                     db_name=db_name, collection_name=col,
                                                                                     filter_or_bson=filter_,
                                                                                     projection=projection,
                                                                                     sort=sort, limit=limit)
        
        return success, conn_problem, values_list, error_message
    
    
    # Lê um documento de uma collection
    async def read_one(self, db_name, col, filter_={}, projection={})-> tuple[bool, bool, dict, str]:
        if not self.__conn[0]: # verifica a conexão
            success, error_message = await self.check_and_retry_connection()
            if not success:
                error_message = f"[read_one] Erro ao ler do mongo: {error_message}"
                return False, error_message
            
        success, conn_problem, value, error_message = await find_one_from_mongo(client_mongo=self.__conn[1],
                                                                           db_name=db_name, collection_name=col,
                                                                           filter_or_bson=filter_,
                                                                           projection=projection)

        return success, conn_problem, value, error_message
    

    # Atualiza um documento de uma collection
    async def update_one(self, db_name, col, filter_={}, update_={}, operator='$set', upsert=True)-> tuple[bool, bool, str]:
        if not self.__conn[0]: # verifica a conexão
            success, error_message = await self.check_and_retry_connection()
            if not success:
                error_message = f"[update_one] Erro ao ler do mongo: {error_message}"
                return False, error_message
            
        sucess, conn_problem, error_message = await update_in_mongo(client_mongo=self.__conn[1],
                                                                           db_name=db_name, collection_name=col,
                                                                           filter_or_bson=filter_,
                                                                           updatedata_or_bson=update_,
                                                                           operator=operator,
                                                                           upsert=upsert)
        
        return sucess, conn_problem, error_message

     # Atualiza vários documento de uma collection
    async def update_many(self, db_name, col, filter_={}, update_={}, operator='$set', upsert=True)-> tuple[bool, bool, str]:
        if not self.__conn[0]: # verifica a conexão
            success, error_message = await self.check_and_retry_connection()
            if not success:
                error_message = f"[update_one] Erro ao ler do mongo: {error_message}"
                return False, error_message
            
        sucess, conn_problem, error_message = await update_many_in_mongo(client_mongo=self.__conn[1],
                                                                           db_name=db_name, collection_name=col,
                                                                           filter_or_bson=filter_,
                                                                           updatedata_or_bson=update_,
                                                                           operator=operator,
                                                                           upsert=upsert)
        
        return sucess, conn_problem, error_message


    # Deleta um documento de uma collection e retorna o documento deletado
    async def delete_one(self, db_name, col, filter_={}) -> tuple[bool, bool, dict, str]:
        if not self.__conn[0]: # verifica a conexão
            success, error_message = await self.check_and_retry_connection()
            if not success:
                error_message = f"[delete_one] Erro ao ler do mongo: {error_message}"
                return False, error_message
            
        success, conn_problem, deleted_doc, error_message = await find_and_delete_from_mongo(client_mongo=self.__conn[1],
                                                                                db_name=db_name, collection_name=col,
                                                                                filter_or_bson=filter_)
        
        return success, conn_problem, deleted_doc, error_message
