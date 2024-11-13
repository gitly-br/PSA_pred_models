from sanic import Blueprint, response

bp_modelo_1 = Blueprint('modelo_1', url_prefix='/modelo_1')

@bp_modelo_1.route('/', methods=['GET'])
async def get_modelo_1(request):
    return response.json({'message': 'Hello from modelo_1!'})
