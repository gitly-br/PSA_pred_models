from sanic import Blueprint, response
from app.utils.openweather import get_OW_mongo_data_and_agg
from app.utils.inferencia import inferencia_previsao
from app.utils.encode_json import encode_body

bp_modelo_3 = Blueprint('modelo_3', url_prefix='/modelo_3')

@bp_modelo_3.route('/', methods=['POST'])
async def get_modelo_3(request):

    args = request.json

    if args is None:
        args = {}

    succ, resp = await inferencia_previsao(request, args.get('modelo', "lgbm_sa_1"), args.get('regiao', 'SA'))

    if succ:
        return response.json({'status' : 'success', 'data' : encode_body(resp)})

    else:
        return response.json({'status' : 1, 'data' : encode_body(resp)})
