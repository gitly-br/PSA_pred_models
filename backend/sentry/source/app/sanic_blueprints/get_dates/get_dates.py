from datetime import datetime, timezone, timedelta
from sanic import Blueprint, response
from motor.motor_asyncio import AsyncIOMotorClient
import os

bp_get_dates = Blueprint('get_dates', url_prefix='/get_dates')

@bp_get_dates.listener('before_server_start')
async def setup_db(app, loop):
    app.ctx.mongo_client_dates = AsyncIOMotorClient(os.environ.get("MONGO_URI"), io_loop=loop)

@bp_get_dates.listener('after_server_stop')
async def close_db(app, loop):
    app.ctx.mongo_client_dates.close()

@bp_get_dates.route('/', methods=['GET'])
async def get_get_dates(request):
    mongo = request.app.ctx.mongo_client_dates

    date_set = set()

    try:
        inference_coll = mongo.floodcast.inference
        cursor = inference_coll.find({}, projection={'dt_key': 1}).sort('dt_key', -1)
        for doc in await cursor.to_list(length=None):
            dt = doc.get('dt_key')
            if dt:
                date_set.add(dt.isoformat()[:10])
    except Exception:
        pass

    try:
        forecast_coll = mongo.api_data.forecast
        cursor = forecast_coll.find({}, projection={'dt_request': 1}).sort('dt_request', -1)
        for doc in await cursor.to_list(length=None):
            dt = doc.get('dt_request')
            if dt:
                date_set.add(dt.isoformat()[:10])
    except Exception:
        pass

    sorted_dates = sorted(date_set, reverse=True)

    return response.json({
        'success': True,
        'conn_problem': False,
        'dates': sorted_dates,
        'err_mg': '',
    })
