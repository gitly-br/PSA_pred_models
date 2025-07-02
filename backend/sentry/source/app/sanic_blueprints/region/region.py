from sanic import Blueprint
from sanic.response import json
from motor.motor_asyncio import AsyncIOMotorClient
from app.common.utils.log_config import setup_logger
import os
from datetime import datetime, time
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

@bp_region.listener('before_server_start')
async def setup_db(app, loop):
    app.ctx.mongo_client = AsyncIOMotorClient('mongodb://host.docker.internal:27017', io_loop=loop)
    app.ctx.db = app.ctx.mongo_client.floodcast_db

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
            target_date = datetime.now().date()

        # Get the start and end of the day for the target date
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)

        # Find the inference for the given region and date
        inference = await collection.find_one(
            {
                'region': region_name, 
                'dt_key': {
                    '$gte': start_of_day,
                    '$lt': end_of_day
                }
            }
        )
        
        if inference:
            # Convert ObjectId to string for JSON serialization
            inference['_id'] = str(inference['_id'])
            # Convert datetime objects to string for JSON serialization
            if 'dt_inference' in inference and isinstance(inference['dt_inference'], datetime):
                inference['dt_inference'] = inference['dt_inference'].isoformat()
            
            # Convert Decimal128 to float recursively
            inference['results'] = convert_decimal128_to_float(inference['results'])
            
            return json(inference['results'], ensure_ascii=False)
        else:
            return json({'error': f'Inference not found for region {region_name} on date {target_date}'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching data for region {region_name}: {e}")
        return json({'error': 'An internal error occurred'}, status=500)
