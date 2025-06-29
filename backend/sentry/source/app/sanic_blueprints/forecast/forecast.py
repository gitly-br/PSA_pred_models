from sanic import Blueprint, response

bp_forecast = Blueprint("forecast", url_prefix="/forecast")

@bp_forecast.get("/")
async def get_forecast(request):
    return response.json({"status": "success", "data": "This is a placeholder for the forecast route."})