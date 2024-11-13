async def call_OW_api_(request, route, params=None):
    """
    request: request object from sanic (usado para pegar objeto httpx_client para fazer request)
    """



    base_url = 'https://api.openweathermap.org/data/2.5/'
    url = base_url + route

    s = request.app.ctx.settings['openweather']['api_key']
    headers = {
        'Content-Type': 'application/json'
    }
    
    if params is None:
        params = {}
    params['appid'] = s

    payload = {}
    
    response = await request.app.ctx.httpx_client.post(url, headers=headers, json=payload)
    
    return response.json()