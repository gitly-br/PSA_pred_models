from sanic import Blueprint, response
from app.utils.openweather import get_OW_mongo_data_and_agg
from app.utils.inferencia import inferencia_previsao
from app.utils.encode_json import encode_body

bp_modelo_2 = Blueprint('modelo_2', url_prefix='/modelo_2')

@bp_modelo_2.route('/', methods=['POST'])
async def get_modelo_2(request):

    args = request.json

    if args is None:
        args = {}

    resp = await inferencia_previsao(request, args.get('modelo', "rf_sa_1"), args.get('regiao', 'SA'))


    return response.json({'status' : 'success', 'data' : encode_body(resp)})
