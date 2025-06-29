from os import environ
from sanic import Blueprint
from sanic.response import empty, json as sanic_json
from app.common.db_ops.bson_data import encode_bson, deserialize_json
from app.common.errors import error_handler as errors

bp_redis_backs_integration = Blueprint('redis_backs_integration')


@bp_redis_backs_integration.post('<shopping_id>/redis_backs_integration/')
async def PostInfos(request, shopping_id: int):

    request_body = request.json
    ### Exemplo de corpo da requisição
    # {
    #     'mongo': {
    #         'db_name': 'teste_backs',
    #         'col': 'teste',
    #         'filter_': {},
    #         'operator': '$set',
    #         'update_': {'a': 'asd'},
    #         'upsert': True
    #     },
    #     'hash': {
    #         "bff_col": 'aiosndfoub12-93'
    #     }
    # }

    request_body['shopping_id'] = shopping_id

    bson_dict = encode_bson(request_body)
    # aqui é a escolha da Queue
    key_queue = request.app.ctx.sett["KEY_PATTERNS_REDIS"]["Q_UPDATE_DATA"][request.app.ctx.sett['application']]["WRITE"]

    success, conn_problem, err_msg = await request.app.ctx.redis_obj.write_queue(key=key_queue,
                                                                                 value=bson_dict)

    if not success:
        errors.error_gmall(
            redis_client=request.app.ctx.redis_obj,
            settings=request.app.ctx.sett,
            logger=request.app.ctx.logger,
            module="app_sanic/sanic_blueprints/parking",
            e=f'erro ao consultar a rota parking no shopping {shopping_id}',
            log_type="error",
            sub_type="mongo_read",
            file_="source/app/sanic_blueprints/parking/parking.py",
            function="consulta_bff_parking",
            for_debug={"shopping_id": shopping_id, 'error': err_msg},
            severity="high",
            write_in_logger=True
        )

        return sanic_json({'hash': 'aiosndfoub1293'}, 500)

    return sanic_json({'status': 'success', 'resp': 'a'}, status=200)
