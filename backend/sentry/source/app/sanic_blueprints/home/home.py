from sanic import Blueprint, response

bp_home = Blueprint('home', url_prefix='/home')

@bp_home.route('/', methods=['POST', 'GET'])
async def get_home(request):
    return response.json({'status': 'deprecated', 'message': 'This endpoint is deprecated. Please use /region/{region_name} instead.'}, status=404)
