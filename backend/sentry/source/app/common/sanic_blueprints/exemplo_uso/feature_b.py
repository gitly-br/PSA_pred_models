from datetime import datetime
from sanic import Blueprint
from sanic.response import json, empty, text
import app.common.errors.error_handler as errors
from app.common.db_ops.bson_data import encode_bson


feature_b = Blueprint('feature_b', url_prefix='/feature_b')


@feature_b.route('/escrever_queue_redis/<id_:int>', methods=['POST'])
async def post_escrever_no_redis_feature_b(request, id_:int):

    # caso não seja um json, retorna erro
    try:
        if not request.json:
            return json({"message": "Sem corpo de entrada"}, status=400)
        data_dict = request.json
    except Exception as e:
        return json({"message": "Não é um json", "erro": str(e)}, status=400)

    #-----verificar campos que são OBRIGATÓRIOS (caso existam)----
    obrigatorios = ["registro", "outro_obrigatorio"]
    if not all([True if x in data_dict else False for x in obrigatorios]):
        return json({"message": f"Campos obrigatórios não informados: {obrigatorios}"}, status=400)

    # se existir valores invalidos, verificar também. Exemplo, o campo existe mas esta vazio...


    #-----verificar campos que são NECESSARIOS mas que possuem default (caso existam)----
    nome = data_dict.get("nome", "Nome não informado")
    genero = data_dict.get("genero", "Genero não informado")

    #-----verificar campos que são OPCIONAIS (caso existam)----
    opcional = data_dict.get("opcional", None) # opcionais recebem None como default

    # Valor a ser enviado para o Redis
    dict_value = {
        "registro": data_dict["registro"],
        "meu_id": id_,
        "outro_obrigatorio": data_dict["outro_obrigatorio"],
        "nome": nome,
        "genero": genero,
        "opcional": opcional
    }
    bson_dict = encode_bson(dict_value)
    key_queue = request.app.ctx.sett["KEY_PATTERNS_REDIS"]["Q_UPDATE_BACKAPP"] # aqui é a escolha da Queue
    success, conn_problem, err_msg = await request.app.ctx.redis_obj.write_queue(key = key_queue,
                                                                                 value = bson_dict)

    if not success:
        # Utilizar error_handler para enviar para o log_writer e gravar em um arquivo de log local
        await errors.error_in_feature_a(redis_client=request.app.ctx.redis_obj,
                                        settings=request.app.ctx.sett,
                                        logger=request.app.ctx.logger,
                                        for_debug={"dict_value": dict_value},
                                        e=err_msg,
                                        log_type="error",
                                        sub_type="mongo_write",
                                        function="post_escrever_no_mongo_feature_a")

        return json({"message": f"Erro ao escrever no mongo: {err_msg}"}, status=500)

    return json({"message": f"Dado enviado para a Queue: {id_}"}, status=201)


@feature_b.route('/escrever_valor_no_redis/<id_:int>', methods=['POST'])
async def post_escrever_valor_no_redis_feature_b(request, id_:int):

    # caso não seja um json, retorna erro
    try:
        if not request.json:
            return json({"message": "Sem corpo de entrada"}, status=400)
        data_dict = request.json
    except Exception as e:
        return json({"message": "Não é um json", "erro": str(e)}, status=400)

    #-----verificar campos que são OBRIGATÓRIOS (caso existam)----
    obrigatorios = ["registro", "outro_obrigatorio"]
    if not all([True if x in data_dict else False for x in obrigatorios]):
        return json({"message": f"Campos obrigatórios não informados: {obrigatorios}"}, status=400)

    # se existir valores invalidos, verificar também. Exemplo, o campo existe mas esta vazio...


    #-----verificar campos que são NECESSARIOS mas que possuem default (caso existam)----
    nome = data_dict.get("nome", "Nome não informado")
    genero = data_dict.get("genero", "Genero não informado")

    #-----verificar campos que são OPCIONAIS (caso existam)----
    opcional = data_dict.get("opcional", None) # opcionais recebem None como default

    # Valor a ser enviado para o Redis
    dict_value = {
        "registro": data_dict["registro"],
        "meu_id": id_,
        "outro_obrigatorio": data_dict["outro_obrigatorio"],
        "nome": nome,
        "genero": genero,
        "opcional": opcional
    }
    bson_dict = encode_bson(dict_value)
    key = "ALGUMA_KEY"#request.app.ctx.sett["KEY_PATTERNS_REDIS"]["Q_UPDATE_BACKAPP"] # aqui é a escolha da Queue
    success, conn_problem, err_msg = await request.app.ctx.redis_obj.write_redis_bson(key = key,
                                                                                      value = bson_dict)

    if not success:
        # Utilizar error_handler para enviar para o log_writer e gravar em um arquivo de log local
        await errors.error_in_feature_a(redis_client=request.app.ctx.redis_obj,
                                        settings=request.app.ctx.sett,
                                        logger=request.app.ctx.logger,
                                        for_debug={"dict_value": dict_value},
                                        e=err_msg,
                                        log_type="error",
                                        sub_type="mongo_write",
                                        function="post_escrever_no_mongo_feature_a")

        return json({"message": f"Erro ao escrever no mongo: {err_msg}"}, status=500)

    return json({"message": f"Dado enviado para o Redis: {id_}"}, status=201)