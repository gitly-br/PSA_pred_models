from sanic import Blueprint, response
from app.utils.openweather import get_OW_mongo_data_and_agg
from app.utils.inferencia import inferencia_previsao

bp_modelo_1 = Blueprint('modelo_1', url_prefix='/modelo_1')

@bp_modelo_1.route('/', methods=['POST'])
async def get_modelo_1(request):

    args = request.json

    resp = await inferencia_previsao(request, args.get('modelo', "xgboost_sa_1"), args.get('regiao', 'SA'))


    return response.json({'status' : 'success', 'data' : resp})
