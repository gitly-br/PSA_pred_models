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


def _aggregate_hourly_forecast(docs: list[dict]) -> list[dict]:
    hourly_buckets: dict[int, list[dict]] = {}
    for doc in docs:
        hourly = doc.get('hourly') or []
        for hour in hourly:
            dt = hour.get('dt')
            hour_idx = dt.hour if isinstance(dt, datetime) else None
            if hour_idx is None:
                continue
            hourly_buckets.setdefault(hour_idx, []).append(hour)

    result = []
    numeric_fields = ['temperature', 'rain', 'precipitation_mm', 'humidity', 'pressure', 'wind_speed', 'dew_point', 'pop', 'clouds']
    for hour_idx in sorted(hourly_buckets):
        items = hourly_buckets[hour_idx]
        averages = {}
        for field in numeric_fields:
            values = [item.get(field) for item in items if isinstance(item.get(field), (int, float))]
            if values:
                averages[field] = sum(values) / len(values)

        entry: dict = {
            'temp': round(averages.get('temperature', 0), 4),
            'rain': round(averages.get('rain') or averages.get('precipitation_mm', 0), 4),
            'pop': round(averages.get('pop', 0), 4),
        }
        if 'humidity' in averages:
            entry['humidity'] = round(averages['humidity'])
        if 'pressure' in averages:
            entry['pressure'] = round(averages['pressure'])
        if 'wind_speed' in averages:
            entry['wind_speed'] = round(averages['wind_speed'], 1)
        if 'dew_point' in averages:
            entry['dew_point'] = round(averages['dew_point'], 1)
        if 'clouds' in averages:
            entry['clouds'] = round(averages['clouds'])
        result.append(entry)

    return result


def _day_bounds(target_date):
    start_time = datetime.combine(target_date, time.min)
    end_time = datetime.combine(target_date + timedelta(days=1), time.min)
    return start_time, end_time

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

        start_time, end_time = _day_bounds(target_date)

        docs = await collection.find({
            'dt_request': {
                '$gte': start_time,
                '$lt': end_time
            }
        }).to_list(length=None)

        if not docs:
            return json([])

        return json(_aggregate_hourly_forecast(docs))

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

        start_time, end_time = _day_bounds(target_date)

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
