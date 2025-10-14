from sanic import Blueprint, response

bp_forecast = Blueprint("forecast", url_prefix="/forecast")

@bp_forecast.route('/', methods=['POST', 'GET'])
async def get_forecast(request):
    return response.json({'status': 'deprecated', 'message': 'This endpoint is deprecated. Please use /region/{region_name} instead.'}, status=404)