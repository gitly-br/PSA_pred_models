from datetime import datetime
from sanic import Blueprint, response

bp_home = Blueprint('home', url_prefix='/home')

@bp_home.route('/', methods=['POST'])
async def get_home(request):

    args = request.json

    if args is None:
        args = {}
    
    
    #TODO define datetime value

    regions = args.get('regions', ['SA', 'MENINOS', 'ORATORIO', 'TAMCENTRAL', 'GUARARA'])

    # Placeholder for removed inference logic
    return response.json({'status' : 'success', 'data' : f"This is a placeholder for the home route. Regions: {regions}"})
