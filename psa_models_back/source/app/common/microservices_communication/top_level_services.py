import redis.asyncio as redis
from app.common.db_ops.bson_data import encode_bson
from app.common.db_ops.redis_ops_v2 import push_key_to_queue

async def send_to_log_writer(redis_client:redis.Redis, settings, db_name=None, col_name=None,
                                type_=None, process=None, data_to_process=None,
                                logger=None)->tuple[bool, bool, str]:

    queue_key = settings["KEY_PATTERNS_REDIS"]["Q_LOG_WRITER"]
    if db_name is None or col_name is None or data_to_process is None:
        return False, False, "Erro ao montar pacote para envio para a fila do log_writer, faltando parametros"

    type_ = "insert_one" if type_ is None else type_
    process = "as_is" if process is None else process

    dict_para_envio_mongo_writer = {
       "db": db_name,
       "col": col_name,
       "type": type_,
       "process": process,
       "data_to_process": data_to_process
    }

    bson_dict = encode_bson(dict_para_envio_mongo_writer)
    success_q, conn_problem, error_message_q = await push_key_to_queue(client_redis=redis_client,
                                                                key=queue_key,
                                                                value_dict_bson=bson_dict,
                                                                push_type="end")

    if not success_q:
        if logger:
            logger.error("Erro ao tentar enviar para a fila: %s", error_message_q)
        return False, conn_problem, error_message_q
    
    return True, None, None



async def send_to_deliverer(redis_client:redis.Redis, data_do_send=None,
                                settings=None, logger=None)->tuple[bool, bool, str]:

    if data_do_send is None:
        return False, False, "Valor de data_do_send não pode ser None"

    queue_key = settings["KEY_PATTERNS_REDIS"]["Q_DELIVERER"]

    bson_dict = encode_bson(data_do_send)    
    success_q, conn_problem, error_message_q = await push_key_to_queue(client_redis=redis_client,
                                                                  key=queue_key,
                                                                  value_dict_bson=bson_dict,
                                                                  push_type="end")
    if not success_q:
        if logger:
            logger.error("Erro ao tentar enviar para a fila: %s", error_message_q)
        return False, conn_problem, error_message_q
    
    return True, None, None