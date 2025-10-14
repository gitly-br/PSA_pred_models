from datetime import datetime
from app.common.microservices_communication.top_level_services import send_to_log_writer
from app.common.db_ops.app_redis_opsv2 import RedisAppOps

db_name = "gitly_logs"
col_name = "gmall"


async def error_gmall(redis_client, settings, logger, for_debug:dict, e:str,
                 log_type:str, sub_type:str, module:str, file_:str, function:str,
                 severity:str, write_in_logger:bool, **kwargs):


        # Enviar para o log_writer, que por sua vez irá enviar ao mongo
        data_to_process= {
            "app_name": "gitly_gmall",
            "processed_at": datetime.utcnow(),
            "log_type": log_type,
            "sub_type": sub_type,
            "module": module,
            "file": file_,
            "function": function,
            "error_message": e,
            "severity": severity,
            "for_debug": for_debug
        }

        success, conn_problem, error_m = await send_to_log_writer(redis_client=redis_client,
                                                                  db_name=db_name, col_name=col_name,
                                                                  data_to_process=data_to_process,
                                                                  settings=settings, logger=logger)

        if not success:
            if logger is not None:
                
                logger.error("[error_gmall] Erro ao enviar para mongo_writer: %s, conn=%b", error_m, conn_problem)
    
        # Gravando em um arquivo de log local
        if write_in_logger:
            str_log = f"[{module}] on function {function} - {e}"
            if severity == "high":
                logger.critical(str_log)
            else:
                logger.error(str_log)

        return True




async def error_in_feature_a(redis_client, settings, logger, for_debug={}, e:str="",
                                log_type:str="crash", sub_type:str="", function:str="", **kwargs):


        # Enviar para o log_writer, que por sua vez irá enviar ao mongo
        data_to_process= {
            "processed_at": datetime.utcnow(),
            "log_type": log_type,
            "sub_type": sub_type,
            "module": "exemplo_uso",
            "file": "feature_a.py",
            "function": function,
            "error_message": e,
            "severity": "high",
            "for_debug": for_debug
        }
    
        success, conn_problem, error_m = await send_to_log_writer(redis_client=redis_client,
                                                                  db_name=db_name, col_name=col_name,
                                                                  data_to_process=data_to_process,
                                                                  settings=settings, logger=logger)

        if not success:
            if logger is not None:
                logger.error("[error_in_feature_a] Erro ao enviar para mongo_writer: %s, conn=%b", error_m, conn_problem)
    

        # Gravando em um arquivo de log local
        if logger is not None:
            logger.error("[%s] Erro: %s", function, e)

        return True # Não tem muito o que fazer caso dê erro aqui, então apenas retorna True

async def error_security(redis_client, settings, logger, sub_type:str, module:str,
                         file_:str, severity:str, for_debug:dict, e:str,
                         function:str, write_in_logger:bool=False, **kwargs):


    return await error_gmall(redis_client=redis_client,
                        settings=settings,
                        logger=logger,
                        log_type = "security",
                        sub_type = sub_type,
                        module = module,
                        file_ = file_,
                        function = function,
                        severity = severity,
                        for_debug=for_debug, e=e,
                        write_in_logger=write_in_logger)
