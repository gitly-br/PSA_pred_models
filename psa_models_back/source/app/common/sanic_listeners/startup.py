# Listeners relacionados ao início da aplicação
import asyncio
from logging import Logger
import random
from app.common.db_ops.app_redis_opsv2 import RedisAppOps
from app.common.db_ops.app_mongo_ops import MongoAppOps


async def load_data_from_mongo_to_redis(main_mongo:MongoAppOps, main_redis:RedisAppOps, settings:dict, server_num:int, logger:Logger)->tuple[bool, str]:
    pass


# Testando a conexão com o Redis e Mongo antes de continuar, caso tenha algum load inicial de carga do Mongo para o Redis
# aqui é o lugar que colocaremos
async def init_redis_and_mongo(logger:Logger, settings:dict)->tuple[bool, str]:
    # Inicializa a conexão com redis e mongo
    # Primeiro verificar conexão com o Mongo, antes de entrar no looping de tentar virar master do Redis para realizar a carga
    main_mongo = MongoAppOps(settings=settings)
    sucess_mongo, error_message_mongo = await main_mongo.init_connection(minPoolSize=1, maxPoolSize=2)
    if not sucess_mongo:
        # Certificando que não ficarão conexões zoombies e não vazamento de memória
        await main_mongo.close_all_connections()
        del main_mongo
        error_message = f"[init_redis_and_mongo] Mongo Connection Error: {error_message_mongo}"
        logger.error(error_message)
        return False, error_message

    logger.debug("[init_redis_and_mongo] Mongo Connection Success")

    # # Criando objeto de gerenciamento do Redis
    # main_redis = RedisAppOps(settings=settings)
    # success_redis, error_message_redis = await main_redis.init_connections(max_conn=1)
    # if not success_redis:
    #     await main_mongo.close_all_connections()
    #     del main_mongo
    #     await main_redis.close_all_connections()
    #     del main_redis
    #     return False, error_message_redis

    # logger.debug("[init_redis_and_mongo] Redis Connection Success")




    ###
    # Código de carga aqui, apenas carga inicial, cuidado com conflito com outros webservices que poderão tentar fazer a mesma coisa
    # Ta com ddúvida? Pergunte ao Tiago
    ###



    # Certificando que não ficarão conexões zoombies e não vazamento de memória
    # await main_redis.close_all_connections()
    await main_mongo.close_all_connections()
    # del main_redis
    del main_mongo
    return True, None
