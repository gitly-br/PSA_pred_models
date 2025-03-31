from sanic import Blueprint, response
from sanic.exceptions import InvalidUsage

from app.utils.openweather import get_OW_mongo_data_for_dash
from app.utils.encode_json import encode_body

bp_forecast = Blueprint("forecast", url_prefix="/forecast")

@bp_forecast.get("/")
async def get_forecast(request):
    dt_begin = request.headers.get("dt_begin")

    data = await get_OW_mongo_data_for_dash(request, dt_begin)
    
    # Example response using dt_begin as a filter
    return response.json({"status": "success", "data": encode_body(data)})