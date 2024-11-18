import asyncio
from datetime import datetime


async def get_openweather_api_data(app, route, params=None):
        
    while True:
        
        token = app.ctx.sett['API_KEYS']['openweather']

        res_forecast = await app.ctx.httpx_client.get(f'http://api.openweathermap.org/data/2.5/forecast?lat=-23.667548&lon=-46.528934&appid={token}&units=metric')

        datas = res_forecast.json()

        datas['dt_request'] = datetime.now()

        # Inserir registro em mongo

        await app.ctx.mongo_obj.write_one(db_name='api_data',
            col='openweather_col',
            doc=datas)
        
        
        await asyncio.sleep(3600*1.45)