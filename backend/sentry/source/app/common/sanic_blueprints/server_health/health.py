from sanic import response
from sanic import Blueprint
import multiprocessing

health = Blueprint('health', url_prefix='/health')

@health.route('/', methods=['GET'])
async def api_health(request):
    return response.json({"message": "API is up and running!"})

@health.route('/cpu', methods=['GET'])
async def cpu_and_workers_count(request):
    cpus = multiprocessing.cpu_count()
    workers_ = "<implementar depois>"
    return response.json({"cpu": cpus, "workers": workers_})


@health.route('/config', methods=['GET'])
async def sanic_config(request):
    config = request.app.config
    print(config)
    return response.json({"config": config})