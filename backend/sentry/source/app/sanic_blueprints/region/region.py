from sanic import Blueprint
from sanic.response import json
from motor.motor_asyncio import AsyncIOMotorClient
from app.common.utils.log_config import setup_logger
import os
import asyncio
import sys
from datetime import datetime, time, timezone, timedelta
from bson.decimal128 import Decimal128

bp_region = Blueprint('region', url_prefix='/region')

# Configure logging
env = os.environ.get('env', 'dev')
success_log, logger = setup_logger(env=env, name_process="region_blueprint")

def convert_decimal128_to_float(obj):
    if isinstance(obj, Decimal128):
        return float(str(obj))
    if isinstance(obj, dict):
        return {k: convert_decimal128_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimal128_to_float(elem) for elem in obj]
    return obj


async def _trigger_floodcast(target_date: datetime.date) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "floodcast.main", "--date", target_date.isoformat()]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = (stdout or b"").decode("utf-8", errors="replace") + (stderr or b"").decode("utf-8", errors="replace")
    return proc.returncode == 0, output.strip()


async def _get_municipal_inference(collection, target_date: datetime.date, target_hour: int | None = None):
    """Fetch the closest municipal inference for the given date.

    If target_hour is provided, returns the inference whose dt_key is closest
    to that hour on the target date (e.g. 01:30 -> 01:00). Otherwise returns
    the most recent inference on that day.
    """
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)
    query = {
        'region': 'all',
        'dt_key': {
            '$gte': start_of_day,
            '$lt': end_of_day,
        },
    }
    if target_hour is not None:
        # Compute the absolute difference in minutes from target_hour:00
        pipeline = [
            {'$match': query},
            {'$addFields': {
                'hour_diff': {
                    '$abs': {
                        '$subtract': [
                            {'$hour': '$dt_key'},
                            target_hour
                        ]
                    }
                }
            }},
            {'$sort': {'hour_diff': 1, 'dt_key': -1}},
            {'$limit': 1}
        ]
        docs = await collection.aggregate(pipeline).to_list(length=1)
        return docs[0] if docs else None
    else:
        # Most recent inference on that day
        return await collection.find_one(
            query,
            sort=[('dt_key', -1)]
        )


def _missing_region_message(inference: dict, region_name: str, target_date: datetime.date) -> str | None:
    region_errors = inference.get("region_errors") or {}
    missing = region_errors.get(region_name)
    if not missing:
        return None
    missing_text = " e ".join(missing)
    return f"Inference not found for region {region_name} on date {target_date}: faltando dado de {missing_text}"

@bp_region.listener('before_server_start')
async def setup_db(app, loop):
    app.ctx.mongo_client = AsyncIOMotorClient(os.environ.get("MONGO_URI"), io_loop=loop)
    app.ctx.db = app.ctx.mongo_client.floodcast

@bp_region.listener('after_server_stop')
async def close_db(app, loop):
    app.ctx.mongo_client.close()

@bp_region.route('/<region_name>')
async def get_region_inference(request, region_name):
    try:
        collection = request.app.ctx.db.inference
        date_str = request.args.get('date')
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return json({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
        else:
            target_date = datetime.now(timezone(timedelta(hours=-3))).date() 

        # Use the current hour in Sao Paulo for approximate matching
        now_sp = datetime.now(timezone(timedelta(hours=-3)))
        target_hour = now_sp.hour

        inference = await _get_municipal_inference(collection, target_date, target_hour=target_hour)

        if not inference:
            ok, output = await _trigger_floodcast(target_date)
            if ok:
                inference = await _get_municipal_inference(collection, target_date, target_hour=target_hour)
            else:
                logger.error(f"Fallback Floodcast failed for region {region_name}: {output}")
                # If Floodcast explicitly reported missing data, surface that to the client
                if "Sem dados para inferencia" in output:
                    return json({"error": output}, status=404)
                return json({"error": f"Inference generation failed for {region_name} on date {target_date}: {output}"}, status=500)

        if inference:
            # Convert ObjectId to string for JSON serialization
            inference['_id'] = str(inference['_id'])
            # Convert datetime objects to string for JSON serialization
            if 'dt_inference' in inference and isinstance(inference['dt_inference'], datetime):
                inference['dt_inference'] = inference['dt_inference'].isoformat()
            
            # Convert Decimal128 to float recursively
            inference['results'] = convert_decimal128_to_float(inference['results'])

            day_key = next(iter(inference['results'].keys()), None)
            if not day_key:
                return json({'error': 'Inference payload is empty'}, status=404)

            day_payload = inference['results'][day_key]
            if region_name == 'all':
                return json(day_payload.get('all', {}), ensure_ascii=False)

            region_payload = day_payload.get(region_name)
            if region_payload:
                return json(region_payload, ensure_ascii=False)

            missing_message = _missing_region_message(inference, region_name, target_date)
            if missing_message:
                return json({"error": missing_message}, status=404)

            ok, output = await _trigger_floodcast(target_date)
            if ok:
                inference = await _get_municipal_inference(collection, target_date, target_hour=target_hour)
                if inference:
                    inference['results'] = convert_decimal128_to_float(inference['results'])
                    inference['region_errors'] = convert_decimal128_to_float(inference.get('region_errors') or {})
                    day_key = next(iter(inference['results'].keys()), None)
                    if day_key:
                        day_payload = inference['results'][day_key]
                        if region_name == 'all':
                            return json(day_payload.get('all', {}), ensure_ascii=False)
                        region_payload = day_payload.get(region_name)
                        if region_payload:
                            return json(region_payload, ensure_ascii=False)
                        missing_message = _missing_region_message(inference, region_name, target_date)
                        if missing_message:
                            return json({"error": missing_message}, status=404)

            logger.error(f"Fallback Floodcast failed for region {region_name}: {output}")
            if "Sem dados para inferencia" in output:
                return json({"error": output}, status=404)
            return json({"error": f"Inference generation failed for {region_name} on date {target_date}: {output}"}, status=500)

        else:
            return json({'error': f'Inference not found for region {region_name} on date {target_date}'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching data for region {region_name}: {e}")
        return json({'error': 'An internal error occurred'}, status=500)
