from datetime import datetime
from sanic import Blueprint, response
from app.utils.openweather import get_OW_mongo_data_and_agg
from app.utils.inferencia import inferencia_geral, inferencia_previsao_2
from app.utils.encode_json import encode_body

bp_home = Blueprint('home', url_prefix='/home')

@bp_home.route('/', methods=['POST'])
async def get_home(request):

    args = request.json

    if args is None:
        args = {}
    
    
    #TODO define datetime value

    regions = args.get('regions', ['SA', 'MENINOS', 'ORATORIO', 'TAMCENTRAL', 'GUARARA'])

    succ, resp = await inferencia_geral(request, regions, args.get('dt_request', datetime.now().isoformat()))


    if succ:
        return response.json({'status' : 'success', 'data' : encode_body(resp)})

    else:
        return response.json({'status' : 1, 'data' : encode_body(resp)})
