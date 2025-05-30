from datetime import datetime
from sanic import Blueprint, response
from app.utils.openweather import get_OW_mongo_data_and_agg
from app.utils.inferencia import inferencia_previsao
from app.utils.encode_json import encode_body

bp_get_dates = Blueprint('get_dates', url_prefix='/get_dates')

@bp_get_dates.route('/', methods=['GET'])
async def get_get_dates(request):

    success, conn_problem, dates, err_mg = await request.app.ctx.mongo_obj.read_all(
        db_name='api_data',
        col='openweather_col',
        filter_={},
        projection={'_id': 0, 'dt_request': 1},
        sort=[('dt_request', 1)]
    )

    date_set = set()
    for i in dates:
        date_set.add((i['dt_request']).date().isoformat())

    return response.json({'success': success, 'conn_problem': conn_problem, 'dates': encode_body(list(date_set)), 'err_mg': err_mg})