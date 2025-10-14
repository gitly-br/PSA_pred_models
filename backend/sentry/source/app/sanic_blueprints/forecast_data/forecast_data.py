from sanic import Blueprint
from sanic.response import json
from motor.motor_asyncio import AsyncIOMotorClient
from app.common.utils.log_config import setup_logger
import os
from datetime import datetime, time, timezone, timedelta

bp_forecast_data = Blueprint('forecast_data', url_prefix='/forecast-data')

# Configure logging
env = os.environ.get('env', 'dev')
success_log, logger = setup_logger(env=env, name_process="forecast_data_blueprint")

def get_target_date(request):
    date_str = request.args.get('date')
    if date_str:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None
    return datetime.now(timezone(timedelta(hours=-3))).date()

@bp_forecast_data.listener('before_server_start')
async def setup_db(app, loop):
    app.ctx.mongo_client_harvest = AsyncIOMotorClient(os.environ.get("MONGO_URI"), io_loop=loop)
    app.ctx.db_harvest = app.ctx.mongo_client_harvest.harvest_data

@bp_forecast_data.listener('after_server_stop')
async def close_db(app, loop):
    app.ctx.mongo_client_harvest.close()

@bp_forecast_data.route('/<region>/<sourcename>')
async def get_forecast_data(request, region, sourcename):
    try:
        target_date = get_target_date(request)
        if not target_date:
            return json({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        collection_name = f"{sourcename}_{region}_all"
        collection = request.app.ctx.db_harvest[collection_name]

        # Define the time range for the query (3:00:00 to 3:59:59 UTC)
        start_time = datetime.combine(target_date, time(3, 0, 0))
        end_time = datetime.combine(target_date, time(3, 59, 59))

        # Find the data for the given region, sourcename, and time range
        data = await collection.find_one({
            'dt_request': {
                '$gte': start_time,
                '$lt': end_time
            }
        })

        if data:
            if 'hourly' in data:
                return json(data['hourly'])
            else:
                return json({'error': f'\'hourly\' key not found in data for {region} - {sourcename} on {target_date} at 3 AM UTC'}, status=404)
        else:
            return json({'error': f'Data not found for {region} - {sourcename} on {target_date} at 3 AM UTC'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching data for {region} - {sourcename}: {e}")
        return json({'error': 'An internal error occurred'}, status=500)
