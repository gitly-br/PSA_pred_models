from sanic import Blueprint
from sanic.response import json
from motor.motor_asyncio import AsyncIOMotorClient
from app.common.utils.log_config import setup_logger
import os
from datetime import datetime, time, timezone, timedelta

bp_forecast_data = Blueprint('forecast_data', url_prefix='/forecast-data')

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
    app.ctx.db_harvest = app.ctx.mongo_client_harvest.api_data

@bp_forecast_data.listener('after_server_stop')
async def close_db(app, loop):
    app.ctx.mongo_client_harvest.close()

@bp_forecast_data.route('/')
async def get_aggregated_forecast_data(request):
    try:
        target_date = get_target_date(request)
        if not target_date:
            return json({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        collection = request.app.ctx.db_harvest['forecast']

        start_time = datetime.combine(target_date, time(3, 0, 0))
        end_time = datetime.combine(target_date, time(3, 59, 59))

        docs = await collection.find({
            'dt_request': {
                '$gte': start_time,
                '$lt': end_time
            }
        }).to_list(length=None)

        if not docs:
            return json([])

        hourly_buckets: dict[int, list[dict]] = {}
        for doc in docs:
            hourly = doc.get('hourly') or []
            for h in hourly:
                dt = h.get('dt')
                if not dt:
                    continue
                if isinstance(dt, datetime):
                    hour_idx = dt.hour
                else:
                    hour_idx = 0
                if hour_idx not in hourly_buckets:
                    hourly_buckets[hour_idx] = []
                hourly_buckets[hour_idx].append(h)

        result = []
        for hour_idx in sorted(hourly_buckets.keys()):
            items = hourly_buckets[hour_idx]
            n = len(items)
            averages = {}
            numeric_fields = ['temperature', 'rain', 'precipitation_mm', 'humidity', 'pressure', 'wind_speed', 'dew_point', 'pop', 'clouds']
            for field in numeric_fields:
                values = [item.get(field) for item in items if isinstance(item.get(field), (int, float))]
                if values:
                    averages[field] = sum(values) / len(values)

            entry: dict = {
                'temp': averages.get('temperature', 0),
                'rain': averages.get('rain') or averages.get('precipitation_mm', 0),
                'pop': averages.get('pop', 0),
            }
            if 'humidity' in averages:
                entry['humidity'] = round(averages['humidity'])
            if 'pressure' in averages:
                entry['pressure'] = round(averages['pressure'])
            if 'wind_speed' in averages:
                entry['wind_speed'] = round(averages['wind_speed'], 1)
            if 'dew_point' in averages:
                entry['dew_point'] = round(averages['dew_point'], 1)

            result.append(entry)

        return json(result)

    except Exception as e:
        logger.error(f"Error fetching aggregated forecast data: {e}")
        return json({'error': 'An internal error occurred'}, status=500)

@bp_forecast_data.route('/<region>/<sourcename>')
async def get_forecast_data_by_source(request, region, sourcename):
    try:
        target_date = get_target_date(request)
        if not target_date:
            return json({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        collection_name = f"{sourcename}_{region}_all"
        collection = request.app.ctx.db_harvest[collection_name]

        start_time = datetime.combine(target_date, time(3, 0, 0))
        end_time = datetime.combine(target_date, time(3, 59, 59))

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
