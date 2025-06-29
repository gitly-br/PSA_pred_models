from datetime import datetime
from sanic import Blueprint
from sanic.response import json, empty, text
import app.common.errors.error_handler as errors


feature_a = Blueprint('feature_a', url_prefix='/feature_a')

@feature_a.route('/op_no_mongo/<id_:int>', methods=['GET'])
async def get_ler_do_mongo_feature_a(request, id_:int):

    #-----verificar campos que são OBRIGATÓRIOS (caso existam)----

    #-----verificar campos que são NECESSARIOS mas que possuem default (caso existam)----

    #-----verificar campos que são OPCIONAIS (caso existam)----

    # criar objeto de filtro e projeção para leitura no Mongo, mesmo que fique vazio
    db_name = "exemplo_uso"
    collection = "teste_col"
    filter_ = {
        "meu_id": id_
        }
    projection = {"_id": 0}
    success, conn_problem, value, err_msg = await request.app.ctx.mongo_obj.read_one(db_name=db_name,
                                                                               col=collection,
                                                                               filter_=filter_,
                                                                               projection=projection)

    if not success:
        # Utilizar error_handler para enviar para o log_writer e gravar em um arquivo de log local
        await errors.error_in_feature_a(redis_client=request.app.ctx.redis_obj,
                                        settings=request.app.ctx.sett,
                                        logger=request.app.ctx.logger,
                                        for_debug={"id": id_},
                                        e=err_msg,
                                        log_type="error",
                                        sub_type="mongo_read",
                                        function="get_ler_do_mongo_feature_a")

        return json({"message": f"Erro ao ler do mongo: {err_msg}"}, status=500)

    # value será None caso não tenha encontrado nenhum documento com o id
    if value is None:
        return json({"message": f"Não foi encontrado nenhum documento com id={id_}"}, status=404)

    return json({"message": f"Feature A: {id_}", "value": value})





@feature_a.route('/op_no_mongo', methods=['GET'])
async def get_ler_varios_do_mongo_feature_a(request):

    #-----verificar campos que são OBRIGATÓRIOS (caso existam)----

    #-----verificar campos que são NECESSARIOS mas que possuem default (caso existam)----

    #-----verificar campos que são OPCIONAIS (caso existam)----

    # criar objeto de filtro e projeção para leitura no Mongo, mesmo que fique vazio
    db_name = "exemplo_uso"
    collection = "teste_col"
    filter_ = {}
    projection = {"_id": 0}
    success, conn_problem, values, err_msg = await request.app.ctx.mongo_obj.read_all(db_name=db_name,
                                                                               col=collection,
                                                                               filter_=filter_,
                                                                               projection=projection)

    if not success:
        # Utilizar error_handler para enviar para o log_writer e gravar em um arquivo de log local
        await errors.error_in_feature_a(redis_client=request.app.ctx.redis_obj,
                                        settings=request.app.ctx.sett,
                                        logger=request.app.ctx.logger,
                                        for_debug={},
                                        e=err_msg,
                                        log_type="error",
                                        sub_type="mongo_read",
                                        function="get_ler_varios_do_mongo_feature_a")

        return json({"message": f"Erro ao ler do mongo: {err_msg}"}, status=500)

    # value será None caso não tenha encontrado nenhum documento com o id
    if values is None:
        return json({"message": f"Não foi encontrado nenhum documento"}, status=404)

    return json({"message": f"Valores recuperados com sucesso", "values": values})






@feature_a.route('/op_no_mongo/<id_:int>', methods=['POST'])
async def post_escrever_no_mongo_feature_a(request, id_:int):

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

    # criar objeto de filtro e projeção para leitura no Mongo, mesmo que fique vazio
    db_name = "exemplo_uso"
    collection = "teste_col"
    doc = {
        "registro": data_dict["registro"],
        "meu_id": id_,
        "outro_obrigatorio": data_dict["outro_obrigatorio"],
        "nome": nome,
        "genero": genero,
        "opcional": opcional
    }
    success, conn_problem, err_msg = await request.app.ctx.mongo_obj.write_one(db_name=db_name,
                                                                               col=collection,
                                                                               doc=doc)

    if not success:
        # Utilizar error_handler para enviar para o log_writer e gravar em um arquivo de log local
        await errors.error_in_feature_a(redis_client=request.app.ctx.redis_obj,
                                        settings=request.app.ctx.sett,
                                        logger=request.app.ctx.logger,
                                        for_debug={"doc": doc},
                                        e=err_msg,
                                        log_type="error",
                                        sub_type="mongo_write",
                                        function="post_escrever_no_mongo_feature_a")

        return json({"message": f"Erro ao escrever no mongo: {err_msg}"}, status=500)

    return json({"message": f"Feature A escrita: {id_}"}, status=201)
