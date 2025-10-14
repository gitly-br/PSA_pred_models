import os
from copy import deepcopy
from redis.backoff import ExponentialBackoff
from redis.asyncio.retry import Retry
import redis.asyncio as redis
from redis.exceptions import ConnectionError as ConnectionErrorRedis
from redis.exceptions import DataError
from redis.exceptions import ResponseError
from app.common.db_ops.bson_data import encode_bson, decode_bson, deserialize_json


# Carregando as infos das maquinas redis, para não ficar passando as configurações toda a hora
# a ideia de abstração desse arquivo é que ele lide com todo o gerenciamento relacionado ao redis
# Verifica se existe conexão com o redis
async def is_connection_active(client_redis:redis.Redis)->bool:
    try:
        response = await client_redis.ping()
        return response
    except Exception:
        return False

# Tenta conectar ao redis e retorna a conexão e um booleano indicando se a conexão foi bem sucedida
async def create_redis_connection(redis_settings, server_num, db_index=0, max_conn:int=None, retry_count:int=1, backoff_factor=1)->tuple[bool, redis.Redis, str]:

    error_message = None
    retry = Retry(ExponentialBackoff(cap=5, base=backoff_factor), retries=retry_count)
    try:
        client_redis = await redis.Redis(
            host= redis_settings['SERVER_ALIAS'][server_num],
            port= redis_settings['SERVER_PORT'][server_num],
            password= redis_settings['PASS'],
            username= redis_settings['USER'],
            db= db_index,
            decode_responses=False,
            encoding= "utf-8",
            max_connections= max_conn,
            retry_on_timeout=True,
            retry=retry,
            socket_connect_timeout=10,
            health_check_interval=15,
        )
        connected = await is_connection_active(client_redis)
        if connected:
            return True, client_redis, None
        else:
            error_message = "[create_redis_connection] Não foi possivel se conectar ao redis"
            return False, None, error_message
    except Exception as e:
        error_message = f"[create_redis_connection] Não foi possivel se conectar ao redis: {e}"
        return False, None, error_message


# Verifica a conexão e tenta reconectar ao redis
async def reconnect_redis_connection(client_redis:redis.Redis, redis_settings, server_num:int=0, db_index:int=0, max_conn:int=None, retry_count:int=1, backoff_factor=1)->tuple[bool, redis.Redis, str]:
    error_message = None
    # verifica a conexão
    success = await is_connection_active(client_redis)
    if not success:
        # se não conseguir, tenta reconectar
        try:
            await client_redis.aclose()
        except Exception:
            pass
        success, client_redis, error_message = await create_redis_connection(redis_settings=redis_settings, server_num=server_num,
                                                                             db_index=db_index, max_conn=max_conn, retry_count=retry_count, 
                                                                             backoff_factor=backoff_factor)
        if success:
            return True, client_redis, None
        else:
            return False, None, error_message
    else:
        return True, client_redis, None


# escreve um dict no redis usando a key passada
async def set_key_redis(client_redis:redis.Redis, key:str, value, ttl_seconds:int=None, keepttl:bool=False) -> tuple[bool, bool, str]:
    error_message = None
    try:
        await client_redis.set(key, value, ex=ttl_seconds, keepttl=keepttl)
        return True, False, None
    # if it was conection error, to try after reconnect
    except (ConnectionError, ConnectionResetError, TimeoutError) as e:
        error_message = f"[set_redis] ConnectionError: {str(e)}"
        return False, True, error_message
    except (DataError, ResponseError) as e:
        error_message = f"[set_redis] DataError: {str(e)}"
        return False, False, error_message
    except Exception as e:
        error_message = f"[set_redis] Erro ao tentar escrever no redis: {str(e)}"
        return False, False, error_message

# Escrever no redis
async def set_key_redis_bson(client_redis:redis.Redis, key:str, value, ttl_seconds:int=None, keepttl:bool=False)->tuple[bool, bool, str]: # success, connection_problem, error_message
    error_message = None
    try:
        if isinstance(value, dict):
            # transformar em bson
            bson_value = encode_bson(value)
        elif isinstance(value, bytes):
            bson_value = value
        else:
            error_message = f"[set_redis] Valor não suportado: {type(value)}, precisa ser dict ou bson"
            return False, False, error_message

        await client_redis.set(key, bson_value, ex=ttl_seconds, keepttl=keepttl)
        return True, False, None
    # if it was conection error, to try after reconnect
    except (ConnectionError, ConnectionResetError, TimeoutError) as e:
        error_message = f"[set_key_redis_bson] ConnectionError: {str(e)}"
        return False, True, error_message
    except (DataError, ResponseError) as e:
        error_message = f"[set_key_redis_bson] DataError: {str(e)}"
        return False, False, error_message
    except Exception as e:
        error_message = f"[set_key_redis_bson] Erro ao tentar escrever no redis: {str(e)}"
        return False, False, error_message

# Ler chave do redis
async def get_key_redis(client_redis: redis.Redis, key:str)->tuple[bool, bool, dict, str]: # success, connection_problem, error_message, value
    error_message = None
    try:
        value = await client_redis.get(key)
        if value is None:
            # Operação foi um sucesso, mas não encontrou a chave
            return True, False, None, None
        else:
            # transformar em dict
            if isinstance(value, bytes): # vem em ytes apenas da queue. aqui é só decodificar utf-8
                try:
                    value_dict = value.decode("utf-8")
                except UnicodeDecodeError:
                    value_dict = decode_bson(value)
                    if isinstance(value_dict, str):
                        value_dict = deserialize_json(value_dict)

            elif isinstance(value, dict):
                value_dict = value
            elif isinstance(value, str):
                value_dict = deserialize_json(value) # Nome ruim, é um simples dump de json
            else:
                raise ValueError(f"Valor não suportado: {type(value)}, precisa ser dict ou bson")
            return True, False, value_dict, None
    except (ConnectionError, ConnectionResetError, TimeoutError) as e:
        error_message = f"[get_key_redis] ConnectionError: {str(e)}"
        return False, True, None, error_message
    except ValueError as e:
        error_message = f"[get_key_redis] ValueError: {str(e)}"
        return False, False, None, error_message
    except (DataError, ResponseError) as e:
        error_message = f"[get_key_redis] DataError: {str(e)}"
        return False, False, error_message
    except Exception as e:
        error_message = f"[get_key_redis] Erro ao tentar ler no redis: {str(e)}"
        return False, False, None, error_message

# Ler chave do redis
async def get_key_redis_bson(client_redis: redis.Redis, key:str)->tuple[bool, bool, dict, str]: # success, connection_problem, error_message, value
    error_message = None
    try:
        value = await client_redis.get(key)
        if value is None:
            # Operação foi um sucesso, mas não encontrou a chave
            return True, False, None, None
        else:
            # transformar em dict
            if isinstance(value, bytes):
                value_dict = decode_bson(value)
                if isinstance(value_dict, str):
                    value_dict = deserialize_json(value_dict)

            elif isinstance(value, dict):
                value_dict = value
            elif isinstance(value, str):
                value_dict = deserialize_json(value) # Nome ruim, é um simples dump de json
            else:
                raise ValueError(f"Valor não suportado: {type(value)}, precisa ser dict ou bson")
            return True, False, value_dict, None
    except (ConnectionError, ConnectionResetError, TimeoutError) as e:
        error_message = f"[get_key_redis_bson] ConnectionError: {str(e)}"
        return False, True, None, error_message
    except ValueError as e:
        error_message = f"[get_key_redis_bson] ValueError: {str(e)}"
        return False, False, None, error_message
    except (DataError, ResponseError) as e:
        error_message = f"[get_key_redis_bson] DataError: {str(e)}"
        return False, False, error_message
    except Exception as e:
        error_message = f"[get_key_redis_bson] Erro ao tentar ler no redis: {str(e)}"
        return False, False, None, error_message

# lê um dict do redis usando a key passada
#async def get_value_redis_dict(d_redis, key, retry_delay=0.1, retry_count=0)->tuple[bool, dict, dict, str]:
   

# Deletar chave do redis
async def delete_key_redis(client_redis:redis.Redis, key:str)->tuple[bool, bool, str]: # success, connection_problem, error_message
    error_message = None
    try:
        await client_redis.delete(key)
        return True, False, None
    # if it was conection error, to try after reconnect
    except (ConnectionError, ConnectionResetError) as e:
        error_message = f"[delete_key_redis] ConnectionError: {str(e)}"
        return False, True, error_message
    except Exception as e:
        error_message = f"[delete_key_redis] Erro ao tentar deletar no redis: {str(e)}"
        return False, False, error_message


# envia um batch de dados para o redis
async def set_batch_data_bson(client_redis:redis.Redis, data_list)->tuple[bool, bool, str]:

    try:
        # Usando pipeline para fazer operações em batch
        async with client_redis.pipeline() as pipe:
            for data_dict in data_list:
                # Verificando se o dicionário tem exatamente uma entrada
                if len(data_dict) != 1:
                    #[set_batch_data] Dicionário inválido não será adicionado
                    continue # Pula para a próxima iteração

                (key, value) = list(data_dict.items())[0]
                bson_value = encode_bson(value)
                await pipe.set(key, bson_value)
            
            results = await pipe.execute()

        # Aqui, podemos verificar se todos os resultados foram bem-sucedidos.
        # No caso do comando SET, um resultado bem-sucedido é 'OK'.
        if all(results):
            return True, False, None
        else:
            if results.count(True) == 0:
                error_message = f"[set_batch_data_bson] Nenhum dicionário foi adicionado, {len(results)} de {len(results)} falharam."
                return False, False, error_message
            else:
                warning_message = f"[set_batch_data_bson] Nem todos dicionários foram adicionados, {len(results) - sum(results)} de {len(results)} não foram adicionados."
            return True, False, warning_message

    # if it was conection error, to try after reconnect
    except (ConnectionError, ConnectionResetError, TimeoutError) as e:
        error_message = f"[set_batch_data_bson] ConnectionError: {str(e)}"
        return False, True, error_message
    except (DataError, ResponseError) as e:
        error_message = f"[set_batch_data_bson] DataError: {str(e)}"
        return False, False, error_message
    except Exception as e:
        error_message = f"[set_batch_data_bson] Erro ao tentar escrever no redis: {str(e)}"
        return False, True, error_message


# Ler chave de uma fila especifica
async def pop_key_from_queue(client_redis:redis.Redis, waiting_keys, pop_type="start", block_for_timeout=True, timeout=0)->tuple[bool, bool, str, dict, str]:
    try:
        if pop_type == "end":
            if block_for_timeout:
                message = await client_redis.brpop(waiting_keys, timeout=timeout)
            else:
                message = await client_redis.rpop(waiting_keys)
        elif pop_type == "start":
            if block_for_timeout:
                message = await client_redis.blpop(waiting_keys, timeout=timeout)
            else:
                message = await client_redis.lpop(waiting_keys)
        else:
            raise ValueError(f"Tipo de pop não suportado: {pop_type}")

        if message is None:
            return False, False, None, None, None # não encontrou nada na fila
        else:
            key = None
            if isinstance(message, tuple):
                key, value = message
                if isinstance(value, bytes):
                    value_dict = decode_bson(value)
                elif isinstance(value, dict):
                    value_dict = value
                else:
                    raise ValueError(f"Valor não suportado: {type(value)} | {value}, precisa ser bytes")

            elif isinstance(message, bytes):
                value_bson = message
                value_dict = decode_bson(value_bson)
            else:
                raise ValueError(f"Valor não suportado: {type(message)} | {message}, precisa ser tuple ou bytes")

            return True, False, key.decode("utf-8"), value_dict, None
        
    except (ConnectionError, ConnectionResetError, TimeoutError) as e:
        error_message = f"[pop_key_from_queue] ConnectionError: {str(e)}"
        return False, True, None, None, error_message
    except ConnectionErrorRedis as e:
        error_message = f"[pop_key_from_queue] ConnectionErrorRedis: {str(e)}"
        return False, True, None, None, error_message
    except ValueError as e:
        error_message = f"[pop_key_from_queue] ValueError: {str(e)}"
        return False, False, None, None, error_message
    except Exception as e:
        error_message = f"[pop_key_from_queue] Erro ao tentar ler no redis: {str(e)}"
        return False, True, None, None, error_message

# Enviar chave para uma fila especifica
# Queue é sempre sempre sempre bson
async def push_key_to_queue(client_redis:redis.Redis, key:str, value_dict_bson, push_type="end")->tuple[bool, bool, str]:
    try:
        if isinstance(value_dict_bson, dict):
            value_bson = encode_bson(value_dict_bson)
        elif isinstance(value_dict_bson, bytes):
            value_bson = value_dict_bson
        else:
            raise ValueError(f"Valor não suportado: {type(value_dict_bson)}, precisa ser dict ou bson")

        if push_type == "end":
            await client_redis.rpush(key, value_bson)
        elif push_type == "start":
            await client_redis.lpush(key, value_bson)
        else:
            raise ValueError(f"Tipo de push não suportado: {push_type}")
        

        return True, False, None
    except (ConnectionError, ConnectionResetError, TimeoutError) as e:
        error_message = f"[push_key_to_queue] ConnectionError: {str(e)}"
        return False, True, error_message
    except ValueError as e:
        error_message = f"[push_key_to_queue] ValueError: {str(e)}"
        return False, False, error_message
    except (DataError, ResponseError) as e:
        error_message = f"[push_key_to_queue] DataError: {str(e)}"
        return False, False, error_message
    except Exception as e:
        error_message = f"[push_key_to_queue] Erro ao tentar escrever no redis: {str(e)}"
        return False, True, error_message


# para ser usado sempre que precisar configurar ou atualizar o TTL de uma chave, lógica para sessão de usuarios principalmente
async def update_key_ttl(client_redis:redis.Redis, key:str, ttl_seconds:int) -> tuple[bool, bool, str]:
    """
    Atualiza o TTL (Time-to-Live) de uma chave específica no Redis.

    Args:
    - d_redis (dict): O dicionário contendo a conexão com o Redis e outras informações.
    - key (str): A chave cujo TTL você deseja atualizar.
    - ttl_seconds (int): O novo valor de TTL em segundos.

    Returns:
    - tuple[bool, str]: Retorna (True, "Mensagem de sucesso") se o TTL for atualizado com sucesso, 
                       (False, "Mensagem de erro") caso contrário.
    """
    try:
        await client_redis.expire(key, ttl_seconds)
        return True, False, None
    except (ConnectionError, ConnectionResetError) as e:
        error_message = f"Erro de conexão ao atualizar TTL: {e}"
        return False, True, error_message
    except Exception as e:
        error_message = f"Erro ao atualizar TTL: {e}"
        return False, False, error_message

async def close_redis_connection(client_redis:redis.Redis)->tuple[bool, str]:
    try:
        if client_redis:
            await client_redis.aclose()
            return True, None
    except Exception as e:
        return False, f"Erro ao fechar a conexão com o Redis: {e}"