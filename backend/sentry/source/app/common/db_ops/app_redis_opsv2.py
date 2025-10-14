# Abstração a nivel de aplicação
# Esse arquivo é a abstração das operações do comuns utilizadas pelo app no redis, como por exemplo: conectar ao primario, conectar ao secundario, ler no primario, ler no secundario, escrever no primario, escrever no secundario, etc.
import asyncio
from copy import deepcopy
import random
from app.common.db_ops.redis_ops_v2 import create_redis_connection, is_connection_active, \
    delete_key_redis, get_key_redis_bson, set_key_redis_bson, close_redis_connection, \
    set_batch_data_bson, get_key_redis, set_key_redis, push_key_to_queue, pop_key_from_queue
from app.common.microservices_communication.top_level_services import send_to_log_writer

# Carregando as infos das maquinas redis, para não ficar passando as configurações toda a hora
# a ideia de abstração desse arquivo é que ele lide com todo o gerenciamento relacionado ao redis
global_redis_settings = {}

class RedisAppOps:

    def __init__(self, settings:dict, is_data_logger: bool = False  ):

        if is_data_logger:
            self.__redis_settings = deepcopy(settings["REDIS_DATA_LOGGER"])
        else:
            self.__redis_settings = deepcopy(settings["REDIS"])
            
        self.__using = 0
        self.max_con = self.__redis_settings.get("NMAX_CONN", 200)
        self.db_index = self.__redis_settings.get("R_ALL_DB_INDEX", 0)
        self.recovery = {
            "last_retry_timestamp":0,
            "try_every_seconds": 5,
        }
        self.__conn = []
        self.__conn.append( [False, None] )
        self.__conn.append( [False, None] )

        self._lock = asyncio.Lock()

    def __enter__(self):
        return self

    async def __exit__(self, exc_type, exc_val, exc_tb):
        await self.close_all_connections()

    # inicializa conexões para a api_keys com o redis
    async def init_connections(self, max_conn=None):
        error_message_pri = None
        error_message_sec = None
        db_index = self.__redis_settings["R_ALL_DB_INDEX"]
        if max_conn==0:
            self.max_con = max_conn
        # antes de abrir mais uma conexão, verificar se ela não existe de fato
        primary_server = await is_connection_active(self.__conn[0][1])
        # se não tem conexão, cria
        if not primary_server:
            success_a, error_message_pri = await self.__conn_primary_redis_server(self.max_con, db_index)

        secundary_server = await is_connection_active(self.__conn[1][1])
        # se não tem conexão, cria
        if not secundary_server:
            success_b, error_message_sec = await self.__conn_secundary_redis_server(self.max_con, db_index)

        if ((primary_server or success_a) or (secundary_server or success_b)):
            return True, None

        # junta as mensagens de erro
        error_message = f"[init_connections] Pri: {error_message_pri} - Sec: {error_message_sec}"
        return False, error_message


    # finalizando todas as conexões ativas
    async def close_all_connections(self):
        # fechar conexões com o dbindex de apikey e config
        if await is_connection_active(self.__conn[0][1]):
            await close_redis_connection(self.__conn[0][1]) # primário
            self.__conn[0] = [False, None]
        if await is_connection_active(self.__conn[1][1]):
            await close_redis_connection(self.__conn[1][1]) # secundário
            self.__conn[1] = [False, None]

    # verificar se existe pelo menos uma conexão ativa
    async def check_if_has_connection_at_least_in_one_server(self)->bool:

        server_0 = await is_connection_active(self.__conn[0][1])
        server_1 = await is_connection_active(self.__conn[1][1])

        return server_0 or server_1

    # conectar ao servidor primario, nível alto de acoplamento pois estamos definindo para o cenário atual
    async def __conn_primary_redis_server(self, max_conn=None, db_index=0)->tuple[bool, str]:

        sucess, redis_client, error_message = await create_redis_connection( server_num=0,
                                                                        db_index=db_index,
                                                                        max_conn=max_conn,
                                                                        redis_settings=self.__redis_settings)
        self.__conn[0] = [sucess, redis_client]
        if not sucess:
            return False, error_message
        
        return True, None

    # sevridor secundário
    async def __conn_secundary_redis_server(self, max_conn=50, db_index=0)->tuple[bool, dict, str]:

        sucess, redis_client, error_message = await create_redis_connection(server_num=1,
                                                                       db_index=db_index,
                                                                       max_conn=max_conn,
                                                                       redis_settings=self.__redis_settings)
        self.__conn[1] = [sucess, redis_client]
        if not sucess:
            return False, error_message

        return True, None


    # Realiza a leitura do redis
    async def read_redis_bson(self, key_search)->tuple[bool, bool, dict, str]:

        temp_using = self.__using
        # realizar a leitura utilizando o servidor self.using
        redis_client = self.__conn[temp_using][1]
        sucess, connection_problem, value, error_message = await get_key_redis_bson(client_redis=redis_client,
                                                                                key=key_search)
        if sucess:
            return True, False, value, None # se der tudo certo, já sai da função
        else:
            if connection_problem:
                # worker irá tentar novamente em outro servidor
                temp_using = 1 if temp_using == 0 else 0
                redis_client = self.__conn[temp_using][1]
                sucess, connection_problem, value, error_message = await get_key_redis_bson(client_redis=redis_client,
                                                                                        key=key_search)
                if sucess:
                    async with self._lock:
                        self.__using = temp_using
                    return True, False, value, None
                else:
                    if connection_problem:
                        # significa que ambos estão fora do ar
                        error_message = f"[read_redis_bson] Ambos servidores estão fora: {error_message}"
                        return False, True, None, error_message

        # Se chegou aqui, significa que não conseguiu ler do redis, mas não é um problema de conexão
        error_message = f"[read_redis_bson] Error: {error_message}"
        return False, False, None, error_message

    # Realiza a leitura do redis
    async def read_redis(self, key_search)->tuple[bool, bool, dict, str]:

        temp_using = self.__using
        # realizar a leitura utilizando o servidor self.using
        redis_client = self.__conn[temp_using][1]
        sucess, connection_problem, value, error_message = await get_key_redis(client_redis=redis_client,
                                                                                key=key_search)
        if sucess:
            return True, False, value, None # se der tudo certo, já sai da função
        else:
            if connection_problem:
                # worker irá tentar novamente em outro servidor
                temp_using = 1 if temp_using == 0 else 0
                redis_client = self.__conn[temp_using][1]
                sucess, connection_problem, value, error_message = await get_key_redis(client_redis=redis_client,
                                                                                        key=key_search)
                if sucess:
                    async with self._lock:
                        self.__using = temp_using
                    return True, False, value, None
                else:
                    if connection_problem:
                        # significa que ambos estão fora do ar
                        error_message = f"[read_redis_bson] Ambos servidores estão fora: {error_message}"
                        return False, True, None, error_message

        # Se chegou aqui, significa que não conseguiu ler do redis, mas não é um problema de conexão
        error_message = f"[read_redis_bson] Error: {error_message}"
        return False, False, None, error_message


    # escreve em um servidor especifico, hard_server_num é o numero do servidor que deve ser escrito
    async def write_redis_bson_hardservernum(self, key, value, hard_server_num:int = None, ttl_seconds:int=None, keepttl:bool=False ) -> tuple[bool, bool, str]:

        if hard_server_num is None:
            error_message = "[write_redis_bson_hardservernum] hard_server_num None"
            return False, False, error_message

        temp_using = hard_server_num
        redis_client = self.__conn[temp_using][1]
        success, conn_problem, error_message = await set_key_redis_bson(client_redis=redis_client,
                                                                        key=key,
                                                                        value=value,
                                                                        ttl_seconds=ttl_seconds,
                                                                        keepttl=keepttl)
        return success, conn_problem, error_message

    # escreve em um servidor especifico, hard_server_num é o numero do servidor que deve ser escrito
    async def write_redis_dict_hardservernum(self, key, value, hard_server_num:int = None, ttl_seconds:int=None, keepttl:bool=False ) -> tuple[bool, bool, str]:

        if hard_server_num is None:
            error_message = "[write_redis_bson_hardservernum] hard_server_num None"
            return False, False, error_message

        temp_using = hard_server_num
        redis_client = self.__conn[temp_using][1]
        success, conn_problem, error_message = await set_key_redis(client_redis=redis_client,
                                                                        key=key,
                                                                        value=value,
                                                                        ttl_seconds=ttl_seconds,
                                                                        keepttl=keepttl)
        return success, conn_problem, error_message


    # escreve no redis
    async def write_redis_bson(self, key, value, ttl_seconds:int=None, keepttl:bool=False ) -> tuple[bool, bool, str]:

        temp_using = self.__using
        # realizar a leitura utilizando o servidor self.using
        redis_client = self.__conn[temp_using][1]
        sucess, connection_problem, error_message = await set_key_redis_bson(client_redis=redis_client,
                                                                            key=key,
                                                                            value=value,
                                                                            ttl_seconds=ttl_seconds,
                                                                            keepttl=keepttl)
        if sucess:
            return True, False, None # se der tudo certo, já sai da função
        else:
            if connection_problem:
                # worker irá tentar novamente em outro servidor
                temp_using = 1 if temp_using == 0 else 0
                redis_client = self.__conn[temp_using][1]
                sucess, connection_problem, error_message = await set_key_redis_bson(client_redis=redis_client,
                                                                                        key=key,
                                                                                        value=value,
                                                                                        ttl_seconds=ttl_seconds,
                                                                                        keepttl=keepttl)
                if sucess:
                    async with self._lock:
                        self.__using = temp_using
                    return True, False, None
                else:
                    if connection_problem:
                        # significa que ambos estão fora do ar
                        error_message = f"[write_redis_bson] Ambos servidores estão fora: {error_message}"
                        return False, True, error_message

    # escreve no redis
    async def write_redis(self, key, value, ttl_seconds:int=None, keepttl:bool=False ) -> tuple[bool, bool, str]:

        temp_using = self.__using
        # realizar a leitura utilizando o servidor self.using
        redis_client = self.__conn[temp_using][1]
        sucess, connection_problem, error_message = await set_key_redis(client_redis=redis_client,
                                                                            key=key,
                                                                            value=value,
                                                                            ttl_seconds=ttl_seconds,
                                                                            keepttl=keepttl)
        if sucess:
            return True, False, None # se der tudo certo, já sai da função
        else:
            if connection_problem:
                # worker irá tentar novamente em outro servidor
                temp_using = 1 if temp_using == 0 else 0
                redis_client = self.__conn[temp_using][1]
                sucess, connection_problem, error_message = await set_key_redis(client_redis=redis_client,
                                                                                        key=key,
                                                                                        value=value,
                                                                                        ttl_seconds=ttl_seconds,
                                                                                        keepttl=keepttl)
                if sucess:
                    async with self._lock:
                        self.__using = temp_using
                    return True, False, None
                else:
                    if connection_problem:
                        # significa que ambos estão fora do ar
                        error_message = f"[write_redis_bson] Ambos servidores estão fora: {error_message}"
                        return False, True, error_message    
    

    # escreve batch em um servidor especifico, hard_server_num é o numero do servidor que deve ser escrito
    async def write_batch_redis_bson_hardservernum(self, data_list, hard_server_num:int = None ) -> tuple[bool, bool, str]:

        if hard_server_num is None:
            error_message = "[write_redis_bson_hardservernum] hard_server_num None"
            return False, False, error_message
        
        temp_using = hard_server_num
        redis_client = self.__conn[temp_using][1]
        success, conn_problem, error_message = await set_batch_data_bson(client_redis=redis_client,
                                                                         data_list=data_list)
        return success, conn_problem, error_message


    # verificar coneção com o dbindex da queue
    async def is_both_queue_active(self)->bool:
        pri = await is_connection_active(self.__conn[0][1]) # primario
        sec = await is_connection_active(self.__conn[1][1]) # secundario
        return pri and sec

    # verifica se pelo menos um dos servidores de queue está ativo
    async def is_at_least_one_queue_active(self)->bool:
        pri = await is_connection_active(self.__conn[0][1]) # primario
        sec = await is_connection_active(self.__conn[1][1]) # secundario
        return pri or sec


    # escreve um doc no redis queue
    #async def push_key_to_queue(client_redis:redis.Redis, key:str, value_dict_bson, push_type="end")->tuple[bool, bool, str]:
    async def write_queue(self, key, value, priority=False) -> tuple[bool, bool, str]:

        temp_using = self.__using
        # realizar a leitura utilizando o servidor self.using
        redis_client = self.__conn[temp_using][1]
        push_type = "end" if not priority else "start"
        sucess, connection_problem, error_message = await push_key_to_queue(client_redis=redis_client,
                                                                            key=key,
                                                                            value_dict_bson=value,
                                                                            push_type=push_type)
        
        if sucess:
            return True, False, None
        else:
            if connection_problem:
                # worker irá tentar novamente em outro servidor
                temp_using = 1 if temp_using == 0 else 0
                redis_client = self.__conn[temp_using][1]
                sucess, connection_problem, error_message = await push_key_to_queue(client_redis=redis_client,
                                                                                        key=key,
                                                                                        value_dict_bson=value,
                                                                                        push_type=push_type)
                if sucess:
                    async with self._lock:
                        self.__using = temp_using
                    return True, False, None
                else:
                    if connection_problem:
                        # significa que ambos estão fora do ar
                        error_message = f"[write_queue] Ambos servidores estão fora: {error_message}"
                        return False, True, error_message
                    
        return False, False, error_message
    

    # escreve para o microservico mongo writer
    async def send_to_mongo_writer_ops(self, db_name=None, col_name=None,
                                    type_=None, process=None, data_to_process=None,
                                    settings=None, logger=None)->tuple[bool, bool, str]:

        temp_using = self.__using
        # realizar a leitura utilizando o servidor self.using
        redis_client = self.__conn[temp_using][1]
        sucess, connection_problem, error_message = await send_to_log_writer(redis_client=redis_client,
                                                                                db_name=db_name,
                                                                                col_name=col_name,
                                                                                type_=type_,
                                                                                process=process,
                                                                                data_to_process=data_to_process,
                                                                                settings=settings,
                                                                                logger=logger)
        if sucess:
            return True, False, None
        else:
            if connection_problem:
                # worker irá tentar novamente em outro servidor
                temp_using = 1 if temp_using == 0 else 0
                redis_client = self.__conn[temp_using][1]
                sucess, connection_problem, error_message = await send_to_log_writer(redis_client=redis_client,
                                                                                        db_name=db_name,
                                                                                        col_name=col_name,
                                                                                        type_=type_,
                                                                                        process=process,
                                                                                        data_to_process=data_to_process,
                                                                                        settings=settings,
                                                                                        logger=logger)
                if sucess:
                    async with self._lock:
                        self.__using = temp_using
                    return True, False, None
                else:
                    if connection_problem:
                        # significa que ambos estão fora do ar
                        error_message = f"[send_to_mongo_writer] Ambos servidores estão fora: {error_message}"
                        return False, True, error_message
        
        return False, False, error_message
    
    # Realiza a leitura de em uma fila do redis e fica preso até que algo seja inserido
    async def read_queue_redis_a(self, waiting_keys)->tuple[bool, bool, dict, str]:
            
            # realizar a leitura utilizando o servidor self.using
            redis_client = self.__conn[0][1] # primario
            success_mes, conn_problem_mes, key_mes, value_dict_mes, error_mes = await pop_key_from_queue(redis_client,
                                                                                            waiting_keys,
                                                                                            pop_type="start",
                                                                                            block_for_timeout=True,
                                                                                            timeout=0)
            
            result_ = {"key": key_mes, "value": value_dict_mes}
            return success_mes, conn_problem_mes, result_, error_mes


    async def read_queue_redis_b(self, waiting_keys)->tuple[bool, bool, dict, str]:
            
            # realizar a leitura utilizando o servidor self.using
            redis_client = self.__conn[1][1] # primario
            success_mes, conn_problem_mes, key_mes, value_dict_mes, error_mes = await pop_key_from_queue(redis_client,
                                                                                            waiting_keys,
                                                                                            pop_type="start",
                                                                                            block_for_timeout=True,
                                                                                            timeout=0)
            
            result_ = {"key": key_mes, "value": value_dict_mes}
            return success_mes, conn_problem_mes, result_, error_mes
    

    # verifica conexão de um servidor redis especifico
    async def check_if_has_connection_at_server_redis_num(self, server_num)->bool:

        server_x = await is_connection_active(self.__conn[server_num][1])
        return server_x
