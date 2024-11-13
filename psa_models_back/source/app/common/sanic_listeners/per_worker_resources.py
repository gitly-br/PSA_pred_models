from app.common.db_ops.app_redis_opsv2 import RedisAppOps
from app.common.db_ops.app_mongo_ops import MongoAppOps
from logging import Logger


async def init_redis_con(settings, is_data_logger: bool = False) -> [bool, RedisAppOps, str]:
    # Inicializa a conexão com redis
    redis_obj = RedisAppOps(settings=settings, is_data_logger=is_data_logger)
    success_redis, error_message_redis = await redis_obj.init_connections()
    if not success_redis:
        del redis_obj
        return False, None, error_message_redis

    success = await redis_obj.check_if_has_connection_at_least_in_one_server()
    if not success:
        await redis_obj.close_all_connections()
        return False, redis_obj, "[init_redis_con] Sem conexão com redis."

    return True, redis_obj, None


async def init_mongo_con(minPoolSize=10, maxPoolSize=None, settings=None) -> [bool, MongoAppOps, str]:

    # MongoDB Initialization
    mongo_obj = MongoAppOps(settings=settings)
    success, error_message = await mongo_obj.init_connection(minPoolSize=minPoolSize, maxPoolSize=maxPoolSize)
    if not success:
        await mongo_obj.close_all_connections()
        del mongo_obj
        return False, None, error_message

    return success, mongo_obj, None
