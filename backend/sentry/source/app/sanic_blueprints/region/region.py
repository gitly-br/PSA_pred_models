from sanic import Blueprint
from sanic.response import json
from motor.motor_asyncio import AsyncIOMotorClient
from app.common.utils.log_config import setup_logger
import os
from datetime import datetime
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
        # Find the most recent inference for the given region
        latest_inference = await collection.find_one(
            {'region': region_name},
            sort=[('dt_inference', -1)]
        )
        if latest_inference:
            # Convert ObjectId to string for JSON serialization
            latest_inference['_id'] = str(latest_inference['_id'])
            # Convert datetime objects to string for JSON serialization
            if 'dt_inference' in latest_inference and isinstance(latest_inference['dt_inference'], datetime):
                latest_inference['dt_inference'] = latest_inference['dt_inference'].isoformat()
            
            # Convert Decimal128 to float recursively
            latest_inference['results'] = convert_decimal128_to_float(latest_inference['results'])
            
            return json(latest_inference['results'], ensure_ascii=False)
        else:
            return json({'error': 'Region not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching data for region {region_name}: {e}")
        return json({'error': 'An internal error occurred'}, status=500)
