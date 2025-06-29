import hashlib
import json
from app.common.db_ops.bson_data import encode_bson, deserialize_json
from app.common.db_ops.app_redis_opsv2 import RedisAppOps
from app.common.errors import error_handler as errors
import asyncio
from datetime import datetime
from bson import ObjectId


def encode_body(body):
    """
    Função para codificar variáveis datetime e ObjectId para string em um corpo JSON.
    """
    def encode_value(value):
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, ObjectId):
            return str(value)
        elif isinstance(value, dict):
            return {key: encode_value(val) for key, val in value.items()}
        elif isinstance(value, list):
            return [encode_value(val) for val in value]
        else:
            return value

    return encode_value(body)


async def update_data_standard(app, key: str, data_dict: dict):

    # Atualização das informações no web service
    # Aqui podemos chamar as atualizações que ocorriam no webhook

    # example of data_dict
    '''
    data_dict = {
        "shopping_id" : 1,
        "mongo": {
            "db_name": "",
            "col": "",
            "filter_": {},
            "delete_op" : True,
            "operator": "",
            "update_": {},
            "upsert": True
        },

        "calc_hash" : True
    }
    '''

    if 'mongo' in data_dict:

        if data_dict.get('mongo').get('delete_op'):
            success, conn_problem, deleted_doc, err_msg = await app.ctx.mongo_obj.delete_one(
                db_name=data_dict['mongo']['db_name'],
                col=data_dict['mongo']['col'],
                filter_=data_dict['mongo']['update_']
            )

            if not success:
                app.ctx.logger.error(f"[update_data_standard_mongo_redis] Erro ao atualizar dados: {err_msg}")
        
        else:
            success, conn_problem, err_msg = await app.ctx.mongo_obj.update_one(
                db_name=data_dict['mongo']['db_name'],
                col=data_dict['mongo']['col'],
                filter_=data_dict['mongo']['filter_'],
                update_=data_dict['mongo']['update_'],
                operator=data_dict['mongo']['operator'],
                upsert=data_dict['mongo']['upsert'],
            )

            if not success:
                app.ctx.logger.error(f"[update_data_standard_mongo_redis] Erro ao atualizar dados: {err_msg}")

        
    if data_dict.get('calc_hash') is True:

        hash_value = hashlib.md5(json.dumps(encode_body(data_dict.get('mongo').get('update_'))).encode("utf-8")).hexdigest()
        
        success, conn_problem, err_msg = await app.ctx.mongo_obj.update_one(
            db_name='db_gmall_users',
            col='app_hash_map_col',
            filter_={'shopping_id': data_dict.get('shopping_id')},
            update_={data_dict.get('mongo').get('col') : hash_value},
            operator='$set',
            upsert=True,
        )

        if not success:
            app.ctx.logger.error(
                f"[update_data_standard_mongo_redis] Erro ao atualizar hashes em mongo: {err_msg}")

        
        success, conn_problem, err_msg = await app.ctx.redis_obj.write_redis(
            f"{app.ctx.sett['KEY_PATTERNS_REDIS']['HASH_APP']}{data_dict.get('shopping_id')}:{data_dict.get('mongo').get('col')}",
            hash_value
        )

        if not success:
            app.ctx.logger.error(
                f"[update_data_standard_mongo_redis] Erro ao atualizar hashes em redis: {err_msg}")

        hash_map = app.ctx.__dict__.setdefault(f"hash_map", {})
        hash_map.setdefault(
            data_dict['shopping_id'], {}).setdefault(key, hash_value)


# O velho webhook de atualização entre os serviços back_admin e back_app
async def receive_update_from_redis(app, worker_id, server_num):
    """
    Função que irá ficar escutando a fila de webhook do Redis
    """

    application = app.ctx.sett["application"]
    key_1 = app.ctx.sett["KEY_PATTERNS_REDIS"]["Q_UPDATE_DATA"][application]["READ"]
    waiting_keys = [key_1]

    app.ctx.logger.info("[receive_update_from_redis] Iniciando a escuta da fila de atualização do Redis %s. (Worker %s)", str(
        server_num), worker_id)

    while True:

        # verifica se tem conexão com redis
        connected = app.ctx.redis_obj.check_if_has_connection_at_server_redis_num(
            server_num)
        if not connected:
            app.ctx.logger.error(
                "[receive_update_from_redis_A] Sem conexao com Redis. (Worker %s)", worker_id)
            await asyncio.sleep(5)
            continue

        while connected:
            try:
                # Receber mensagem do Redis
                s, c_p, resp, err = await app.ctx.redis_obj.read_queue_redis_a(waiting_keys=waiting_keys)
                connected = not c_p
                if s:  # Sucesso
                    # chave, caso esteja olhando para mais de uma fila, a chave te dirá qual foi a fila que recebeu a mensagem
                    key = resp['key']
                    # mensagem já decodificada bson para dict
                    value_dict = resp['value']

                    # Atualização das informações no web service
                    await update_data_standard(app, key, value_dict)

                else:
                    app.ctx.logger.error(
                        "[receive_update_from_redis_A] Erro: %s", err)
                    break

            except Exception as e:
                app.ctx.logger.error(
                    "[receive_update_from_redis_A] Erro: %s", e)
                break


async def send_update_data_via_webhook(app, value_dict: dict) -> tuple[bool, str]:

    application = app.ctx.sett["application"]
    url = app.ctx.sett["WEBHOOKS"]["EMERGENCY_UPDATE_SERVICES"][application]["OTHER_BACK"]

    # verifica se o value_dict é de fato um dicionário
    if not isinstance(value_dict, dict):
        return False, "value_dict não é um dicionário"

    # verifica se o value_dict está vazio
    if not value_dict:
        return False, "value_dict está vazio"

    # Convert data to JSON format
    json_data = serialize_to_json(value_dict)

    # Set the Content-Type header to application/json
    headers = {'Content-Type': 'application/json'}

    response = await app.ctx.httpx_client.post(url, data=json_data, headers=headers)

    if response.status_code == 200:
        return True, None

    return False, f"Erro ao enviar dados para o webhook: {response.status_code}"


# O velho webhook de atualização entre os serviços back_admin e back_app
async def send_update_data(app, value_dict: dict) -> tuple[bool, str]:
    """
    Função que irá ficar escutando a fila de webhook do Redis
    """

    application = app.ctx.sett["application"]
    key = app.ctx.sett["KEY_PATTERNS_REDIS"]["Q_UPDATE_DATA"][application]["WRITE"]

    # verifica se o value_dict é de fato um dicionário
    if not isinstance(value_dict, dict):
        return False, "value_dict não é um dicionário"

    # verifica se o value_dict está vazio
    if not value_dict:
        return False, "value_dict está vazio"

    # encode do value_dict para bson
    bson_data = encode_bson(value_dict)

    # Enviar mensagem para o Redis
    success, conn_problem, e_message = app.ctx.redis_obj.write_queue(
        key, bson_data)

    if success:
        return True, None

    app.ctx.logger.error(
        "[send_update_data] Erro ao enviar dados para o Redis: %s \nTentando via webhook.", e_message)

    s_w, e_w = await send_update_data_via_webhook(app, value_dict)

    return s_w, e_w
